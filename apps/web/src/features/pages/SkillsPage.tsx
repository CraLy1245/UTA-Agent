import { Search, Sparkles } from "lucide-react";
import { PageScaffold } from "./PageScaffold";

export function SkillsPage() {
  return (
    <PageScaffold
      title="技能"
      description="维护可复用工作流，并追踪来源、版本与效果。"
      icon={Sparkles}
      action={<button className="primary-button">新建 Skill</button>}
    >
      <div className="page-toolbar">
        <label>
          <Search />
          <input placeholder="搜索 Skill" />
        </label>
        <select aria-label="Skill 状态">
          <option>活跃 Skill</option>
          <option>已归档</option>
        </select>
        <span>2 / 50 个活跃</span>
      </div>
      <div className="skill-grid">
        <article>
          <Sparkles />
          <div>
            <h2>项目开发协作</h2>
            <p>按阶段读取规范、实施、验证并记录开发状态。</p>
            <dl>
              <div>
                <dt>使用</dt>
                <dd>8</dd>
              </div>
              <div>
                <dt>满意率</dt>
                <dd>100%</dd>
              </div>
              <div>
                <dt>版本</dt>
                <dd>v4</dd>
              </div>
            </dl>
          </div>
        </article>
        <article>
          <Sparkles />
          <div>
            <h2>本地文件安全操作</h2>
            <p>将读写限制在工作区内，并保留可审计记录。</p>
            <dl>
              <div>
                <dt>使用</dt>
                <dd>5</dd>
              </div>
              <div>
                <dt>满意率</dt>
                <dd>80%</dd>
              </div>
              <div>
                <dt>版本</dt>
                <dd>v2</dd>
              </div>
            </dl>
          </div>
        </article>
      </div>
    </PageScaffold>
  );
}
