import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Check, ChevronDown, ChevronUp, ExternalLink, FileUp, FlaskConical, Layers, RefreshCw, Search, Settings, Upload } from "lucide-react";
import { api } from "./api";
import tracnLogo from "./assets/tracn-logo.png";
import type { Direction, DirectionCategory, LlmConfig, LlmConfigCreate, MatchProfileResponse, TeacherDetail, TeacherSummary } from "./types";
import "./styles.css";

type Tab = "teachers" | "categories" | "review" | "match" | "settings";

function App() {
  const [tab, setTab] = useState<Tab>("teachers");
  const [directions, setDirections] = useState<Direction[]>([]);
  const [teachers, setTeachers] = useState<TeacherSummary[]>([]);
  const [pending, setPending] = useState<TeacherSummary[]>([]);
  const [categories, setCategories] = useState<DirectionCategory[]>([]);
  const [selected, setSelected] = useState<TeacherDetail | null>(null);
  const [query, setQuery] = useState("");
  const [direction, setDirection] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");

  const activeTeachers = tab === "review" ? pending : teachers;

  async function loadAll() {
    setLoading(true);
    try {
      const [nextDirections, approvedTeachers, pendingTeachers] = await Promise.all([
        api.directions(),
        api.teachers("approved", query, direction),
        api.teachers("pending", "", "")
      ]);
      setDirections(nextDirections);
      setTeachers(approvedTeachers);
      setPending(pendingTeachers);
      setCategories(await api.directionCategories());
      if (!selected && approvedTeachers[0]) {
        setSelected(await api.teacher(approvedTeachers[0].id));
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll().catch((error) => setNotice(error.message));
  }, []);

  useEffect(() => {
    api.teachers("approved", query, direction).then(setTeachers).catch((error) => setNotice(error.message));
  }, [query, direction]);

  async function openTeacher(id: number) {
    setSelected(await api.teacher(id));
  }

  async function updateWeight(item: Direction, weight: number) {
    const updated = await api.updateDirection(item.id, weight);
    setDirections((items) => items.map((directionItem) => (directionItem.id === updated.id ? updated : directionItem)));
    await loadAll();
  }

  async function approveTeacher(id: number, status: "approved" | "rejected") {
    await api.updateStatus(id, status);
    setNotice(status === "approved" ? "已加入正式导师库" : "已移出候选队列");
    await loadAll();
  }

  async function reclassifyTeachers() {
    const result = await api.reclassifyTeachers();
    setNotice(`AI 重分类完成：已更新 ${result.updated} 位导师`);
    await loadAll();
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><img src={tracnLogo} alt="" /></div>
          <div>
            <h1>TraCN</h1>
            <p>Tracking for Computational Neuroscience</p>
          </div>
        </div>
        <nav>
          <button className={tab === "teachers" ? "active" : ""} onClick={() => setTab("teachers")}>
            <Search size={16} /> 导师筛选
          </button>
          <button className={tab === "categories" ? "active" : ""} onClick={() => setTab("categories")}>
            <Layers size={16} /> 方向分类
          </button>
          <button className={tab === "review" ? "active" : ""} onClick={() => setTab("review")}>
            <Check size={16} /> 审核队列
          </button>
          <button className={tab === "match" ? "active" : ""} onClick={() => setTab("match")}>
            <FileUp size={16} /> AI 匹配
          </button>
          <button className={tab === "settings" ? "active" : ""} onClick={() => setTab("settings")}>
            <Settings size={16} /> 模型设置
          </button>
        </nav>
        <DirectionPanel directions={directions} selected={direction} onSelect={setDirection} onUpdate={updateWeight} />
      </aside>

      <main className="workspace">
        <header className="toolbar">
          <div className="searchbox">
            <Search size={16} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索姓名、单位、方向关键词" />
          </div>
          <button className="icon-button" onClick={() => loadAll()} title="刷新">
            <RefreshCw size={17} className={loading ? "spin" : ""} />
          </button>
        </header>

        {notice && (
          <div className="notice" onClick={() => setNotice("")}>
            {notice}
          </div>
        )}

        {tab === "match" ? (
          <MatchView onOpenTeacher={openTeacher} />
        ) : tab === "settings" ? (
          <SettingsView />
        ) : tab === "categories" ? (
          <CategoryView
            categories={categories}
            selected={selected}
            onOpenTeacher={openTeacher}
            onReclassify={reclassifyTeachers}
            onNotice={setNotice}
          />
        ) : (
          <div className="content-grid">
            <section className="teacher-list">
              <ListHeader tab={tab} count={activeTeachers.length} />
              {tab === "review" && <ImportTools onImported={loadAll} onNotice={setNotice} />}
              {activeTeachers.map((teacher) => (
                <TeacherRow
                  key={teacher.id}
                  teacher={teacher}
                  selected={selected?.id === teacher.id}
                  reviewMode={tab === "review"}
                  onOpen={() => openTeacher(teacher.id)}
                  onApprove={() => approveTeacher(teacher.id, "approved")}
                  onReject={() => approveTeacher(teacher.id, "rejected")}
                />
              ))}
              {!activeTeachers.length && <EmptyState text={tab === "review" ? "暂无待审核候选导师" : "暂无已审核导师"} />}
            </section>
            <TeacherDetailPane teacher={selected} />
          </div>
        )}
      </main>
    </div>
  );
}

function DirectionPanel({
  directions,
  selected,
  onSelect,
  onUpdate
}: {
  directions: Direction[];
  selected: string;
  onSelect: (key: string) => void;
  onUpdate: (item: Direction, weight: number) => void;
}) {
  const [isHidden, setIsHidden] = useState(false);

  return (
    <section className={`direction-panel ${isHidden ? "collapsed" : ""}`}>
      <div className="panel-title">
        <span>方向权重</span>
        <div className="panel-actions">
          <button onClick={() => setIsHidden((value) => !value)} title={isHidden ? "显示方向权重" : "隐藏方向权重"}>
            {isHidden ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
            {isHidden ? "显示" : "隐藏"}
          </button>
          <button onClick={() => onSelect("")}>全部</button>
        </div>
      </div>
      {!isHidden && directions.map((item) => (
        <div className={`direction-item ${selected === item.key ? "selected" : ""}`} key={item.key}>
          <button onClick={() => onSelect(selected === item.key ? "" : item.key)}>{item.name}</button>
          <div className="weight-row">
            <input
              type="range"
              min="0"
              max="5"
              step="0.5"
              value={item.weight}
              onChange={(event) => onUpdate(item, Number(event.target.value))}
            />
            <span>{item.weight.toFixed(1)}</span>
          </div>
        </div>
      ))}
      {isHidden && (
        <div className="direction-collapsed-note">
          <span>已隐藏方向权重</span>
          {selected && <button onClick={() => onSelect("")}>清除方向筛选</button>}
        </div>
      )}
    </section>
  );
}

function ListHeader({ tab, count }: { tab: Tab; count: number }) {
  return (
    <div className="list-header">
      <h2>{tab === "review" ? "候选导师审核" : "导师库"}</h2>
      <span>{count} 条</span>
    </div>
  );
}

function CategoryView({
  categories,
  selected,
  onOpenTeacher,
  onReclassify,
  onNotice
}: {
  categories: DirectionCategory[];
  selected: TeacherDetail | null;
  onOpenTeacher: (id: number) => void;
  onReclassify: () => Promise<void>;
  onNotice: (message: string) => void;
}) {
  const firstKey = categories.find((category) => category.teachers.length)?.direction.key || categories[0]?.direction.key || "";
  const [activeKey, setActiveKey] = useState(firstKey);
  const [isReclassifying, setIsReclassifying] = useState(false);
  const activeCategory = categories.find((category) => category.direction.key === activeKey) || categories[0];
  const institutionGroups = useMemo(() => {
    const groups: { institution: string; teachers: TeacherSummary[] }[] = [];
    for (const teacher of activeCategory?.teachers ?? []) {
      const current = groups[groups.length - 1];
      if (current?.institution === teacher.institution) {
        current.teachers.push(teacher);
      } else {
        groups.push({ institution: teacher.institution, teachers: [teacher] });
      }
    }
    return groups;
  }, [activeCategory]);

  useEffect(() => {
    if (!activeKey && firstKey) {
      setActiveKey(firstKey);
    }
  }, [activeKey, firstKey]);

  async function runReclassify() {
    setIsReclassifying(true);
    try {
      await onReclassify();
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "AI 重分类失败");
    } finally {
      setIsReclassifying(false);
    }
  }

  return (
    <div className="category-layout">
      <section className="category-index">
        <div className="category-head">
          <div>
            <h2>方向分类</h2>
            <span>{categories.reduce((sum, category) => sum + category.teachers.length, 0)} 位</span>
          </div>
          <button onClick={runReclassify} disabled={isReclassifying}>
            {isReclassifying ? "重分类中..." : "AI 重分类"}
          </button>
        </div>
        <div className="category-buttons">
          {categories.map((category) => (
            <button
              className={activeCategory?.direction.key === category.direction.key ? "active" : ""}
              key={category.direction.key}
              onClick={() => setActiveKey(category.direction.key)}
            >
              <strong>{category.direction.name}</strong>
              <span>{category.teachers.length} 位 · 权重 {category.direction.weight.toFixed(1)}</span>
            </button>
          ))}
        </div>
      </section>
      <section className="teacher-list">
        <div className="list-header">
          <h2>{activeCategory?.direction.name || "方向分类"}</h2>
          <span>{activeCategory?.teachers.length || 0} 条</span>
        </div>
        {institutionGroups.map((group) => (
          <div className="institution-group" key={group.institution}>
            <div className="institution-group-title">
              <strong>{group.institution}</strong>
              <span>{group.teachers.length} 位</span>
            </div>
            {group.teachers.map((teacher) => (
              <TeacherRow
                key={teacher.id}
                teacher={teacher}
                selected={selected?.id === teacher.id}
                reviewMode={false}
                onOpen={() => onOpenTeacher(teacher.id)}
                onApprove={() => undefined}
                onReject={() => undefined}
              />
            ))}
          </div>
        ))}
        {!activeCategory?.teachers.length && <EmptyState text="该方向下暂无已归类导师" />}
      </section>
      <TeacherDetailPane teacher={selected} />
    </div>
  );
}

function TeacherRow({
  teacher,
  selected,
  reviewMode,
  onOpen,
  onApprove,
  onReject
}: {
  teacher: TeacherSummary;
  selected: boolean;
  reviewMode: boolean;
  onOpen: () => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  const initials = teacher.name.slice(0, 2);
  return (
    <article className={`teacher-row ${selected ? "selected" : ""}`} onClick={onOpen}>
      <div className="avatar">{teacher.avatar_url ? <img src={teacher.avatar_url} alt="" /> : initials}</div>
      <div className="teacher-main">
        <div className="teacher-line">
          <strong>{teacher.name}</strong>
          <span>{teacher.title || "职称待补充"}</span>
          <b>{teacher.match_score.toFixed(1)}</b>
        </div>
        <div className="meta-line">
          {teacher.institution}
          {teacher.department ? ` · ${teacher.department}` : ""}
          {teacher.city ? ` · ${teacher.city}` : ""}
        </div>
        <p>{teacher.evidence_sentence || teacher.bio || "待补充研究方向证据句"}</p>
        <div className="tag-row">
          {teacher.primary_direction_name && <span>{teacher.primary_direction_name}</span>}
          {teacher.email && <span>{teacher.email}</span>}
        </div>
      </div>
      {reviewMode && (
        <div className="review-actions" onClick={(event) => event.stopPropagation()}>
          <button onClick={onApprove}>通过</button>
          <button className="secondary" onClick={onReject}>
            拒绝
          </button>
        </div>
      )}
    </article>
  );
}

function TeacherDetailPane({ teacher }: { teacher: TeacherDetail | null }) {
  if (!teacher) return <aside className="detail-pane"><EmptyState text="选择一位导师查看详情" /></aside>;
  const homepage = teacher.homepage_url || teacher.lab_url;
  const directionKeywords = teacher.directions.map((item) => item.direction_name);
  return (
    <aside className="detail-pane">
      <div className="detail-head">
        <div>
          <h2>
            {homepage ? (
              <a href={homepage} target="_blank" rel="noreferrer">
                {teacher.name} <ExternalLink size={15} />
              </a>
            ) : (
              teacher.name
            )}
          </h2>
          <p>{teacher.institution} · {teacher.title || "职称待补充"}</p>
        </div>
        <strong>{teacher.match_score.toFixed(1)}</strong>
      </div>
      <section>
        <h3>研究方向</h3>
        {teacher.bio && (
          <div className="source-summary">
            <b>原网页记载</b>
            <p>{teacher.bio}</p>
          </div>
        )}
        {directionKeywords.length > 0 && (
          <div className="direction-keywords">
            <span>分类关键词</span>
            {directionKeywords.map((keyword) => <b key={keyword}>{keyword}</b>)}
          </div>
        )}
      </section>
      <section>
        <h3>联系方式</h3>
        <p>{teacher.email || "邮箱待补充"}</p>
        <p>{teacher.phone || "电话待补充"}</p>
      </section>
      <section>
        <h3>Publications</h3>
        {teacher.publications.length ? teacher.publications.map((pub) => (
          <p className="publication-item" key={pub.id}>{pub.year || ""} {pub.title}</p>
        )) : <p>官方主页暂未提取到发表文章；可通过官方主页继续核对。</p>}
      </section>
      <section>
        <h3>主持项目</h3>
        {teacher.grants.length ? teacher.grants.map((grant) => <p key={grant.id}>{grant.year || ""} {grant.name}</p>) : <p>主持项目信息待补充。</p>}
      </section>
      <section>
        <h3>官方主页</h3>
        {teacher.sources.length ? teacher.sources.map((source) => (
          <a className="source-link" href={source.source_url} target="_blank" rel="noreferrer" key={source.id}>
            <span>{source.source_url}</span> <ExternalLink size={13} />
          </a>
        )) : <p>暂无官方主页链接。</p>}
      </section>
    </aside>
  );
}

function ImportTools({ onImported, onNotice }: { onImported: () => void; onNotice: (message: string) => void }) {
  const [url, setUrl] = useState("");
  const [preview, setPreview] = useState("");

  async function importCsv(file?: File) {
    if (!file) return;
    const result = await api.importCsv(file);
    onNotice(`已导入 ${result.imported} 位候选导师`);
    onImported();
  }

  async function previewUrl() {
    const result = await api.urlPreview(url);
    setPreview(`${result.title}\n${result.text_preview}`);
  }

  return (
    <div className="import-tools">
      <label className="upload-button">
        <Upload size={15} /> 导入 CSV
        <input type="file" accept=".csv" onChange={(event) => importCsv(event.target.files?.[0])} />
      </label>
      <div className="url-preview">
        <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="粘贴官方主页 URL 做抓取预览" />
        <button onClick={previewUrl}>预览</button>
      </div>
      {preview && <pre>{preview}</pre>}
    </div>
  );
}

function MatchView({ onOpenTeacher }: { onOpenTeacher: (id: number) => void }) {
  const [result, setResult] = useState<MatchProfileResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const sorted = useMemo(() => result?.results ?? [], [result]);

  async function upload(file?: File) {
    if (!file) return;
    setBusy(true);
    try {
      setResult(await api.matchProfile(file));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="match-view">
      <div className="match-upload">
        <FlaskConical size={22} />
        <h2>CV / PS 匹配</h2>
        <p>上传文本格式的简历或个人陈述。内容会发送到你在后端 `.env` 配置的外部大模型服务。</p>
        <label className="upload-button">
          <FileUp size={16} /> {busy ? "匹配中..." : "上传并匹配"}
          <input type="file" accept=".txt,.md,.csv" onChange={(event) => upload(event.target.files?.[0])} />
        </label>
      </div>
      {result && (
        <div className="match-results">
          <div className="profile-summary">
            <h3>提取画像</h3>
            <p>{result.extracted_summary}</p>
          </div>
          {sorted.map((item) => (
            <article className="match-row" key={item.teacher.id} onClick={() => onOpenTeacher(item.teacher.id)}>
              <strong>{item.teacher.name}</strong>
              <span>{item.teacher.institution}</span>
              <b>{item.total_score.toFixed(1)}</b>
              <p>{item.reason}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function SettingsView() {
  const [configs, setConfigs] = useState<LlmConfig[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [testMessage, setTestMessage] = useState("");
  const [draft, setDraft] = useState<LlmConfigCreate>({
    name: "",
    provider: "openai-compatible",
    model: "",
    base_url: "",
    api_key: ""
  });

  useEffect(() => {
    loadConfigs().catch((error) => setTestMessage(error.message));
  }, []);

  async function loadConfigs() {
    setConfigs(await api.llmConfigs());
  }

  async function test(id: number | string) {
    const result = await api.testLlmConfig(id);
    setTestMessage(`${result.ok ? "连接成功" : "连接失败"}：${result.message}`);
    await loadConfigs();
  }

  async function selectConfig(id: number | string) {
    await api.selectLlmConfig(id);
    setTestMessage("已切换当前使用的大模型");
    await loadConfigs();
  }

  async function createConfig(event: React.FormEvent) {
    event.preventDefault();
    await api.createLlmConfig(draft);
    setDraft({ name: "", provider: "openai-compatible", model: "", base_url: "", api_key: "" });
    setIsCreating(false);
    setTestMessage("已新建模型配置");
    await loadConfigs();
  }

  if (!configs.length) return <EmptyState text="正在读取模型配置" />;
  return (
    <section className="settings-view">
      <div className="settings-head">
        <h2>模型设置</h2>
        <button onClick={() => setIsCreating((value) => !value)}>{isCreating ? "取消" : "新建"}</button>
      </div>
      {isCreating && (
        <form className="llm-form" onSubmit={createConfig}>
          <label>
            <span>名称</span>
            <input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} required placeholder="例如 DeepSeek V3" />
          </label>
          <label>
            <span>Provider</span>
            <input value={draft.provider} onChange={(event) => setDraft({ ...draft, provider: event.target.value })} required />
          </label>
          <label>
            <span>Model</span>
            <input value={draft.model} onChange={(event) => setDraft({ ...draft, model: event.target.value })} required placeholder="例如 deepseek-chat" />
          </label>
          <label>
            <span>Base URL</span>
            <input value={draft.base_url} onChange={(event) => setDraft({ ...draft, base_url: event.target.value })} required placeholder="https://api.example.com/v1" />
          </label>
          <label>
            <span>API Key</span>
            <input type="password" value={draft.api_key} onChange={(event) => setDraft({ ...draft, api_key: event.target.value })} required placeholder="只保存在本地数据库，不在界面回显" />
          </label>
          <button type="submit">完成</button>
        </form>
      )}
      <div className="llm-grid">
        {configs.map((config) => (
          <article className={`llm-card ${config.is_active ? "active" : ""}`} key={String(config.id)}>
            <div className="llm-card-head">
              <div>
                <h3>{config.name}</h3>
                <span>{config.is_active ? "当前使用" : "可选模型"}</span>
              </div>
              <strong>{config.has_api_key ? "已配置" : "未配置"}</strong>
            </div>
            <dl>
              <dt>Provider</dt><dd>{config.provider}</dd>
              <dt>Model</dt><dd>{config.model}</dd>
              <dt>Base URL</dt><dd>{config.base_url}</dd>
              <dt>{config.is_env ? "API Key 环境变量" : "API Key"}</dt><dd>{config.is_env ? config.api_key_env_name : "stored locally"}</dd>
            </dl>
            <div className="llm-actions">
              <button onClick={() => test(config.id ?? "env")}>测试连接</button>
              {!config.is_active && <button onClick={() => selectConfig(config.id ?? "env")}>使用此模型</button>}
            </div>
          </article>
        ))}
      </div>
      {testMessage && <p className="test-message">{testMessage}</p>}
    </section>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
