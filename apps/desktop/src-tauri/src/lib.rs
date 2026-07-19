use serde::Serialize;
use std::{
    fs::{self, OpenOptions},
    io::{Read, Write},
    net::{SocketAddr, TcpListener, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};
use tauri::{AppHandle, Manager, RunEvent};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

struct BackendState {
    port: u16,
    data_root: PathBuf,
    shutdown_token: String,
    has_secure_api_key: Mutex<bool>,
    child: Mutex<Option<Child>>,
}

#[derive(Serialize)]
struct DesktopBackend {
    api_base_url: String,
    ws_base_url: String,
    data_root: String,
    has_secure_api_key: bool,
}

#[tauri::command]
fn desktop_backend(state: tauri::State<'_, BackendState>) -> DesktopBackend {
    DesktopBackend {
        api_base_url: format!("http://127.0.0.1:{}/api", state.port),
        ws_base_url: format!("ws://127.0.0.1:{}/api/ws", state.port),
        data_root: state.data_root.to_string_lossy().into_owned(),
        has_secure_api_key: state.has_secure_api_key.lock().is_ok_and(|value| *value),
    }
}

fn keychain_entry() -> Result<keyring::Entry, String> {
    keyring::Entry::new("SurvivalAgent", "OPENAI_API_KEY")
        .map_err(|error| format!("cannot access Windows Credential Manager: {error}"))
}

fn read_secure_api_key() -> Option<String> {
    std::env::var("OPENAI_API_KEY")
        .ok()
        .filter(|value| !value.is_empty())
        .or_else(|| keychain_entry().ok()?.get_password().ok())
}

#[tauri::command]
fn store_desktop_api_key(
    value: String,
    state: tauri::State<'_, BackendState>,
) -> Result<(), String> {
    if value.trim().is_empty() {
        return Err("API Key cannot be empty".to_string());
    }
    keychain_entry()?
        .set_password(&value)
        .map_err(|error| format!("cannot save API Key in Windows Credential Manager: {error}"))?;
    if let Ok(mut has_key) = state.has_secure_api_key.lock() {
        *has_key = true;
    }
    Ok(())
}

fn user_data_root(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(override_path) = std::env::var("SURVIVAL_AGENT_DESKTOP_DATA_ROOT") {
        return Ok(PathBuf::from(override_path));
    }
    if let Ok(appdata) = std::env::var("APPDATA") {
        return Ok(PathBuf::from(appdata).join("SurvivalAgent"));
    }
    app.path()
        .app_data_dir()
        .map_err(|error| format!("cannot resolve application data directory: {error}"))
}

fn create_user_directories(root: &Path) -> Result<(), String> {
    for name in ["data", "logs", "workspace", "backups"] {
        fs::create_dir_all(root.join(name))
            .map_err(|error| format!("cannot create {name} directory: {error}"))?;
    }
    Ok(())
}

fn write_launch_error(root: &Path, message: &str) {
    let logs = root.join("logs");
    let _ = fs::create_dir_all(&logs);
    if let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(logs.join("desktop-launch.log"))
    {
        let _ = writeln!(file, "desktop startup failed: {message}");
    }
}

fn sidecar_path(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(path) = std::env::var("SURVIVAL_AGENT_SIDECAR_PATH") {
        return Ok(PathBuf::from(path));
    }
    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|error| format!("cannot resolve resource directory: {error}"))?;
    let executable_name = if cfg!(windows) {
        "survival-agent-api.exe"
    } else {
        "survival-agent-api"
    };
    for candidate in [
        resource_dir.join("resources/sidecar").join(executable_name),
        resource_dir.join("sidecar").join(executable_name),
    ] {
        if candidate.is_file() {
            return Ok(candidate);
        }
    }
    Err(format!(
        "desktop API sidecar is missing under {}",
        resource_dir.display()
    ))
}

fn reserve_port() -> Result<u16, String> {
    TcpListener::bind(("127.0.0.1", 0))
        .and_then(|listener| listener.local_addr())
        .map(|address| address.port())
        .map_err(|error| format!("cannot select a local port: {error}"))
}

fn local_request(port: u16, request: &str) -> std::io::Result<String> {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let mut stream = TcpStream::connect_timeout(&address, Duration::from_millis(300))?;
    stream.set_read_timeout(Some(Duration::from_secs(1)))?;
    stream.write_all(request.as_bytes())?;
    let mut response = String::new();
    stream.read_to_string(&mut response)?;
    Ok(response)
}

fn wait_for_health(port: u16, child: &mut Child) -> Result<(), String> {
    let deadline = Instant::now() + Duration::from_secs(30);
    while Instant::now() < deadline {
        if let Some(status) = child
            .try_wait()
            .map_err(|error| format!("cannot inspect sidecar: {error}"))?
        {
            return Err(format!("desktop API exited before health check: {status}"));
        }
        let request = format!(
            "GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"
        );
        if local_request(port, &request).is_ok_and(|response| response.starts_with("HTTP/1.1 200"))
        {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(150));
    }
    Err("desktop API health check timed out".to_string())
}

fn launch_backend(app: &AppHandle) -> Result<BackendState, String> {
    let data_root = user_data_root(app)?;
    create_user_directories(&data_root)?;
    let executable = sidecar_path(app)?;
    let shutdown_token = uuid::Uuid::new_v4().simple().to_string();
    let api_key = read_secure_api_key();

    for _ in 0..3 {
        let port = reserve_port()?;
        let mut command = Command::new(&executable);
        command
            .arg("--host")
            .arg("127.0.0.1")
            .arg("--port")
            .arg(port.to_string())
            .arg("--data-root")
            .arg(&data_root)
            .env("SURVIVAL_AGENT_DESKTOP_SHUTDOWN_TOKEN", &shutdown_token)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        if let Some(secret) = &api_key {
            command.env("OPENAI_API_KEY", secret);
        }
        #[cfg(windows)]
        command.creation_flags(CREATE_NO_WINDOW);
        let mut child = command
            .spawn()
            .map_err(|error| format!("cannot start desktop API: {error}"))?;
        match wait_for_health(port, &mut child) {
            Ok(()) => {
                return Ok(BackendState {
                    port,
                    data_root,
                    shutdown_token,
                    has_secure_api_key: Mutex::new(api_key.is_some()),
                    child: Mutex::new(Some(child)),
                });
            }
            Err(_) => {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
    Err("desktop API did not become healthy after three attempts".to_string())
}

fn shutdown_backend(state: &BackendState) {
    let request = format!(
        "POST /api/desktop/shutdown HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nX-Survival-Shutdown-Token: {}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
        state.port, state.shutdown_token
    );
    let _ = local_request(state.port, &request);
    if let Ok(mut guard) = state.child.lock() {
        if let Some(mut child) = guard.take() {
            let deadline = Instant::now() + Duration::from_secs(8);
            while Instant::now() < deadline {
                if child.try_wait().ok().flatten().is_some() {
                    return;
                }
                thread::sleep(Duration::from_millis(100));
            }
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

pub fn run() {
    let app = tauri::Builder::default()
        .setup(|app| match launch_backend(&app.handle()) {
            Ok(backend) => {
                app.manage(backend);
                Ok(())
            }
            Err(message) => {
                if let Ok(root) = user_data_root(&app.handle()) {
                    write_launch_error(&root, &message);
                }
                Err(std::io::Error::other(message).into())
            }
        })
        .invoke_handler(tauri::generate_handler![
            desktop_backend,
            store_desktop_api_key
        ])
        .build(tauri::generate_context!())
        .expect("failed to build Survival Agent desktop application");

    app.run(|handle, event| {
        if matches!(event, RunEvent::ExitRequested { .. }) {
            if let Some(state) = handle.try_state::<BackendState>() {
                shutdown_backend(&state);
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reserve_port_returns_bindable_port() {
        let port = reserve_port().expect("port");
        let listener = TcpListener::bind(("127.0.0.1", port)).expect("port remains available");
        assert_eq!(listener.local_addr().expect("address").port(), port);
    }

    #[test]
    fn creates_all_required_user_directories() {
        let root = std::env::temp_dir().join(format!("survival-agent-{}", uuid::Uuid::new_v4()));
        create_user_directories(&root).expect("directories");
        for name in ["data", "logs", "workspace", "backups"] {
            assert!(root.join(name).is_dir());
        }
        fs::remove_dir_all(root).expect("cleanup");
    }
}
