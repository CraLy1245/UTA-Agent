import { Brain, Lock, Search } from "lucide-react";
import { PageScaffold } from "./PageScaffold";

export function MemoryPage() {
  return (
    <PageScaffold
      title="记忆"
      description="查看、筛选并管理 Agent 的长期记忆与实时增量。"
      icon={Brain}
      action={<button className="primary-button">新建记忆</button>}
    >
      <div className="page-toolbar">
        <label>
          <Search />
          <input placeholder="搜索记忆" />
        </label>
        <select aria-label="记忆分类">
          <option>全部分类</option>
          <option>偏好</option>
          <option>项目</option>
        </select>
        <span>7,360 / 20,000 字符</span>
      </div>
      <div className="data-list">
        <article>
          <div>
            <b>长期偏好</b>
            <span>preference</span>
          </div>
          <p>优先选择可维护、可回滚并保留未来选择空间的方案。</p>
          <small>
            <Lock /> 已锁定 · 来源：第 3 回合
          </small>
        </article>
        <article>
          <div>
            <b>当前项目</b>
            <span>project</span>
          </div>
          <p>Survival Agent 正按第 0—9 阶段顺序开发。</p>
          <small>更新于今天 19:12 · 版本 3</small>
        </article>
        <article>
          <div>
            <b>实时增量</b>
            <span className="pending">pending</span>
          </div>
          <p>每次开发前重新读取根目录项目 PDF。</p>
          <small>等待下次认知整理</small>
        </article>
      </div>
    </PageScaffold>
  );
}
