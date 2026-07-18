export interface HealthResponse {
  status: "ok";
  service: string;
  environment: string;
  database: {
    status: "healthy";
    engine: "sqlite";
    journal_mode: string;
  };
}
