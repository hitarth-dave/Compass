import { useState, useEffect } from "react";
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import {
  LayoutGrid,
  MessageSquare,
  BookOpen,
  LogOut,
  Menu,
  ChevronRight,
  ChevronDown,
  Plus,
  MoreHorizontal,
  Pencil,
  Trash2,
  Settings,
  Sun,
  Moon,
  CalendarClock,
  X,
  FolderKanban,
} from "lucide-react";
import { useTheme } from "@/context/ThemeContext";
import { useDisplayMode } from "@/context/DisplayModeContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/context/AuthContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AppShell({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { mode, setMode } = useDisplayMode();
  const [showAdvancedHint, setShowAdvancedHint] = useState(
    () => localStorage.getItem("jyotish_seen_advanced_hint") !== "1"
  );
  const dismissAdvancedHint = () => {
    setShowAdvancedHint(false);
    localStorage.setItem("jyotish_seen_advanced_hint", "1");
  };
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("jyotish_sidebar_collapsed") === "1"
  );
  const [threadsOpen, setThreadsOpen] = useState(true);
  const [threadsExpanded, setThreadsExpanded] = useState(false);
  const [threads, setThreads] = useState([]);
  const THREAD_PREVIEW_COUNT = 9;
  const [renameTarget, setRenameTarget] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(null);

  // Projects — fixed life-area scopes (Marriage, Career, ...), each holding
  // its own set of chats. Lazily loads a project's threads the first time
  // it's expanded rather than fetching all of them up front.
  const [projects, setProjects] = useState([]);
  const [projectsOpen, setProjectsOpen] = useState(false);
  const [expandedProjects, setExpandedProjects] = useState({});
  const [projectThreads, setProjectThreads] = useState({});
  const [projectThreadsLoading, setProjectThreadsLoading] = useState({});

  const displayName = user?.name || "Seeker";
  const activeThread = new URLSearchParams(location.search).get("t");

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("jyotish_sidebar_collapsed", next ? "1" : "0");
  };

  const loadThreads = async () => {
    try {
      const res = await axios.get(`${API}/threads`);
      setThreads(res.data.threads || []);
    } catch (e) {
      // silent
    }
  };

  useEffect(() => {
    loadThreads();
  }, []);

  const loadProjects = async () => {
    try {
      const res = await axios.get(`${API}/projects`);
      setProjects(res.data.projects || []);
    } catch (e) {
      // silent
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    const onThreadsChanged = () => {
      loadThreads();
      Object.keys(expandedProjects).forEach((key) => {
        if (expandedProjects[key]) loadProjectThreads(key);
      });
    };
    window.addEventListener("compass:threads-changed", onThreadsChanged);
    return () => window.removeEventListener("compass:threads-changed", onThreadsChanged);
  }, [expandedProjects]);

  const [addingProject, setAddingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [deleteProjectTarget, setDeleteProjectTarget] = useState(null);

  const submitNewProject = async () => {
    const name = newProjectName.trim();
    if (!name) return;
    try {
      await axios.post(`${API}/projects`, { name });
      setNewProjectName("");
      setAddingProject(false);
      setProjectsOpen(true);
      await loadProjects();
      toast.success("Project added");
    } catch (e) {
      toast.error("Could not add project");
    }
  };

  const doDeleteProject = async () => {
    if (!deleteProjectTarget) return;
    try {
      await axios.delete(`${API}/projects/${deleteProjectTarget.key}`);
      setDeleteProjectTarget(null);
      setProjectThreads((s) => { const next = { ...s }; delete next[deleteProjectTarget.key]; return next; });
      await loadProjects();
      loadThreads(); // its chats fall back into the general Conversation list
      toast.success("Project deleted — its chats moved back to Conversation");
    } catch (e) {
      toast.error("Could not delete project");
    }
  };

  const loadProjectThreads = async (key) => {
    setProjectThreadsLoading((s) => ({ ...s, [key]: true }));
    try {
      const res = await axios.get(`${API}/threads`, { params: { project_key: key } });
      setProjectThreads((s) => ({ ...s, [key]: res.data.threads || [] }));
    } catch (e) {
      // silent
    } finally {
      setProjectThreadsLoading((s) => ({ ...s, [key]: false }));
    }
  };

  const toggleProject = (key) => {
    setExpandedProjects((s) => {
      const next = { ...s, [key]: !s[key] };
      if (next[key] && !projectThreads[key]) loadProjectThreads(key);
      return next;
    });
  };

  const createProjectThread = async (key, label) => {
    try {
      const res = await axios.post(`${API}/threads`, { name: `${label} chat`, project_key: key });
      await loadProjectThreads(key);
      navigate(`/chat?t=${res.data.id}`);
      toast.success("New chat started");
    } catch (e) {
      toast.error("Could not start a new chat");
    }
  };

  // Render's free/hobby backend cold-starts after idling — a request that's
  // still pending 5s in is very likely a cold start, not a slow query.
  // AuthContext's axios interceptor fires this event; dismiss it as soon as
  // anything settles.
  useEffect(() => {
    let toastId;
    const onSlow = () => {
      toastId = toast.loading("Waking up the ephemeris engine… this can take up to a minute on a cold start.");
    };
    const onSettled = () => {
      if (toastId) toast.dismiss(toastId);
    };
    window.addEventListener("compass:slow-request", onSlow);
    window.addEventListener("compass:request-settled", onSettled);
    return () => {
      window.removeEventListener("compass:slow-request", onSlow);
      window.removeEventListener("compass:request-settled", onSettled);
    };
  }, []);

  const createThread = async () => {
    try {
      const res = await axios.post(`${API}/threads`, { name: `Chat ${threads.length + 1}` });
      await loadThreads();
      navigate(`/chat?t=${res.data.id}`);
      toast.success("New chat started");
    } catch (e) {
      toast.error("Could not start a new chat");
    }
  };

  const openRename = (thread) => {
    setRenameTarget(thread);
    setRenameValue(thread.name);
  };

  const doRename = async () => {
    if (!renameTarget || !renameValue.trim()) return;
    await axios.patch(`${API}/threads/${renameTarget.id}`, { name: renameValue.trim() });
    setRenameTarget(null);
    loadThreads();
    if (renameTarget.project_key) loadProjectThreads(renameTarget.project_key);
    toast.success("Renamed");
  };

  const doDelete = async () => {
    if (!deleteTarget) return;
    await axios.delete(`${API}/threads/${deleteTarget.id}`);
    if (activeThread === deleteTarget.id) navigate(`/chat`);
    setDeleteTarget(null);
    loadThreads();
    if (deleteTarget.project_key) loadProjectThreads(deleteTarget.project_key);
    toast.success("Chat deleted");
  };

  const signOut = async () => {
    await logout();
    navigate("/");
  };

  const nav = [
    { to: "/dashboard", label: "Dashboard", Icon: LayoutGrid, testId: "nav-dashboard" },
    { to: "/library", label: "Library", Icon: BookOpen, testId: "nav-library" },
  ];

  return (
    <div className="relative min-h-screen flex" data-testid="app-shell">
      <aside
        className={`shrink-0 border-r border-[color:var(--jai-border)] bg-[color:var(--jai-bg)]/90 backdrop-blur-xl sticky top-0 h-screen flex flex-col z-10 transition-[width] duration-300 ease-out ${
          collapsed ? "w-16" : "w-72"
        }`}
        data-testid="sidebar"
      >
        <div className={`flex items-center gap-3 border-b border-[color:var(--jai-border)] ${collapsed ? "justify-center p-4" : "p-6"}`}>
          <button
            onClick={toggle}
            className="w-9 h-9 rounded-md flex items-center justify-center text-[color:var(--jai-green-deep)] hover:bg-[color:var(--jai-surface)] transition-colors"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            data-testid="sidebar-toggle"
          >
            <Menu size={18} />
          </button>
          {!collapsed && (
            <div className="flex-1 min-w-0 flex items-center">
              <img
                src={theme === "dark" ? "/compass-lockup-dark.png" : "/compass-lockup-light.png"}
                alt="Compass Astro"
                className="h-14 w-auto object-contain"
              />
            </div>
          )}
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {/* Dashboard */}
          <SideItem to="/dashboard" label="Dashboard" Icon={LayoutGrid} collapsed={collapsed} testId="nav-dashboard" />

          {/* Conversation (expandable) */}
          <div>
            <div
              className={`flex items-center rounded-lg transition-colors ${
                location.pathname.startsWith("/chat")
                  ? "bg-[color:var(--jai-surface-2)] text-[color:var(--jai-green-deep)] border border-[color:var(--jai-border)]"
                  : "text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-text)] hover:bg-[color:var(--jai-surface)]/60"
              } ${collapsed ? "px-2 py-3 justify-center" : "px-3 py-2.5"}`}
            >
              <button
                onClick={() => navigate("/chat")}
                className="flex-1 flex items-center gap-3 text-left"
                data-testid="nav-chat"
              >
                <MessageSquare size={17} />
                {!collapsed && <span className="font-medium tracking-wide flex-1">Conversation</span>}
              </button>
              {!collapsed && (
                <button
                  onClick={() => setThreadsOpen((v) => !v)}
                  className="p-1 hover:text-[color:var(--jai-green-deep)]"
                  data-testid="threads-expand"
                >
                  {threadsOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>
              )}
            </div>

            {!collapsed && threadsOpen && (
              <div className="mt-1 ml-5 pl-3 border-l border-[color:var(--jai-border)] space-y-0.5" data-testid="threads-list">
                {(threadsExpanded ? threads : threads.slice(0, THREAD_PREVIEW_COUNT)).map((t) => (
                  <div
                    key={t.id}
                    className={`group flex items-center gap-1 pr-1 rounded-md text-sm ${
                      activeThread === t.id
                        ? "bg-[color:var(--jai-surface-2)] text-[color:var(--jai-green-deep)]"
                        : "hover:bg-[color:var(--jai-surface)]/60 text-[color:var(--jai-text-muted)]"
                    }`}
                    data-testid={`thread-item-${t.id}`}
                  >
                    <button
                      onClick={() => navigate(`/chat?t=${t.id}`)}
                      className="flex-1 text-left px-2 py-1.5 truncate"
                      title={t.name}
                    >
                      {t.name}
                    </button>
                    <DropdownMenu>
                      <DropdownMenuTrigger className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[color:var(--jai-surface-2)]" data-testid={`thread-menu-${t.id}`}>
                        <MoreHorizontal size={13} />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="bg-[color:var(--jai-surface)] border-[color:var(--jai-border)]">
                        <DropdownMenuItem onClick={() => openRename(t)} data-testid={`rename-${t.id}`}>
                          <Pencil size={12} className="mr-2" /> Rename
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setDeleteTarget(t)} className="text-red-700" data-testid={`delete-${t.id}`}>
                          <Trash2 size={12} className="mr-2" /> Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                ))}
                {/* Keep the visible list short (9 by default) so New chat,
                    Library and Settings below stay on-screen without
                    scrolling — "View more" reveals the rest inline. */}
                {threads.length > THREAD_PREVIEW_COUNT && (
                  <button
                    onClick={() => setThreadsExpanded((v) => !v)}
                    className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold-soft)]"
                    data-testid="threads-view-more-btn"
                  >
                    <ChevronDown size={11} className={`transition-transform duration-200 ${threadsExpanded ? "rotate-180" : ""}`} />
                    {threadsExpanded ? "Show fewer" : `View more (${threads.length - THREAD_PREVIEW_COUNT})`}
                  </button>
                )}
                <button
                  onClick={createThread}
                  className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-[color:var(--jai-gold)] hover:text-[color:var(--jai-green-deep)]"
                  data-testid="new-thread-btn"
                >
                  <Plus size={12} /> New chat
                </button>
              </div>
            )}
          </div>

          {/* Projects (expandable) — fixed life-area scopes, each with its
              own chats. A project's thread list is fetched the first time
              it's expanded, not up front. */}
          <div>
            <div
              className={`flex items-center rounded-lg transition-colors text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-text)] hover:bg-[color:var(--jai-surface)]/60 ${
                collapsed ? "px-2 py-3 justify-center" : "px-3 py-2.5"
              }`}
            >
              <button
                onClick={() => setProjectsOpen((v) => !v)}
                className="flex-1 flex items-center gap-3 text-left"
                data-testid="nav-projects"
              >
                <FolderKanban size={17} />
                {!collapsed && <span className="font-medium tracking-wide flex-1">Projects</span>}
              </button>
              {!collapsed && (
                <button
                  onClick={() => setProjectsOpen((v) => !v)}
                  className="p-1 hover:text-[color:var(--jai-green-deep)]"
                  data-testid="projects-expand"
                >
                  {projectsOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>
              )}
            </div>

            {!collapsed && projectsOpen && (
              <div className="mt-1 ml-5 pl-3 border-l border-[color:var(--jai-border)] space-y-0.5" data-testid="projects-list">
                {projects.map((p) => (
                  <div key={p.key}>
                    <div className="group flex items-center gap-1 pr-1 rounded-md">
                      <button
                        onClick={() => toggleProject(p.key)}
                        className="flex-1 flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-[color:var(--jai-text-muted)] hover:bg-[color:var(--jai-surface)]/60 hover:text-[color:var(--jai-text)] min-w-0"
                        data-testid={`project-toggle-${p.key}`}
                      >
                        {expandedProjects[p.key] ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        <span className="flex-1 text-left truncate">{p.label}</span>
                      </button>
                      {p.custom && (
                        <DropdownMenu>
                          <DropdownMenuTrigger className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[color:var(--jai-surface-2)]" data-testid={`project-menu-${p.key}`}>
                            <MoreHorizontal size={13} />
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="bg-[color:var(--jai-surface)] border-[color:var(--jai-border)]">
                            <DropdownMenuItem onClick={() => setDeleteProjectTarget(p)} className="text-red-700" data-testid={`project-delete-project-${p.key}`}>
                              <Trash2 size={12} className="mr-2" /> Delete project
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </div>

                    {expandedProjects[p.key] && (
                      <div className="ml-4 pl-2 border-l border-[color:var(--jai-border)] space-y-0.5" data-testid={`project-threads-${p.key}`}>
                        {projectThreadsLoading[p.key] && (
                          <div className="px-2 py-1.5 text-xs text-[color:var(--jai-text-muted)]">Loading…</div>
                        )}
                        {(projectThreads[p.key] || []).map((t) => (
                          <div
                            key={t.id}
                            className={`group flex items-center gap-1 pr-1 rounded-md text-sm ${
                              activeThread === t.id
                                ? "bg-[color:var(--jai-surface-2)] text-[color:var(--jai-green-deep)]"
                                : "hover:bg-[color:var(--jai-surface)]/60 text-[color:var(--jai-text-muted)]"
                            }`}
                            data-testid={`project-thread-item-${t.id}`}
                          >
                            <button
                              onClick={() => navigate(`/chat?t=${t.id}`)}
                              className="flex-1 text-left px-2 py-1.5 truncate"
                              title={t.name}
                            >
                              {t.name}
                            </button>
                            <DropdownMenu>
                              <DropdownMenuTrigger className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[color:var(--jai-surface-2)]" data-testid={`project-thread-menu-${t.id}`}>
                                <MoreHorizontal size={13} />
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="bg-[color:var(--jai-surface)] border-[color:var(--jai-border)]">
                                <DropdownMenuItem onClick={() => openRename(t)} data-testid={`project-rename-${t.id}`}>
                                  <Pencil size={12} className="mr-2" /> Rename
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => setDeleteTarget(t)} className="text-red-700" data-testid={`project-delete-${t.id}`}>
                                  <Trash2 size={12} className="mr-2" /> Delete
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        ))}
                        {!projectThreadsLoading[p.key] && (projectThreads[p.key] || []).length === 0 && (
                          <div className="px-2 py-1.5 text-xs text-[color:var(--jai-text-muted)]">No chats yet</div>
                        )}
                        <button
                          onClick={() => createProjectThread(p.key, p.label)}
                          className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-[color:var(--jai-gold)] hover:text-[color:var(--jai-green-deep)]"
                          data-testid={`project-new-thread-${p.key}`}
                        >
                          <Plus size={12} /> New chat
                        </button>
                      </div>
                    )}
                  </div>
                ))}

                {addingProject ? (
                  <div className="flex items-center gap-1 px-2 py-1" data-testid="new-project-input-row">
                    <Input
                      autoFocus
                      value={newProjectName}
                      onChange={(e) => setNewProjectName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") submitNewProject();
                        if (e.key === "Escape") { setAddingProject(false); setNewProjectName(""); }
                      }}
                      placeholder="e.g. Health, Kids' education"
                      className="h-7 text-xs bg-transparent border-0 border-b border-[color:var(--jai-border)] rounded-none px-0 focus-visible:ring-0 focus-visible:border-[color:var(--jai-gold)]"
                      data-testid="new-project-input"
                    />
                    <button onClick={submitNewProject} className="p-1 text-[color:var(--jai-gold)] hover:text-[color:var(--jai-green-deep)]" data-testid="new-project-save-btn">
                      <Plus size={12} />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setAddingProject(true)}
                    className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-[color:var(--jai-gold)] hover:text-[color:var(--jai-green-deep)]"
                    data-testid="add-project-btn"
                  >
                    <Plus size={12} /> Add your own project
                  </button>
                )}
              </div>
            )}
          </div>

          <SideItem to="/muhurta" label="Muhurta" Icon={CalendarClock} collapsed={collapsed} testId="nav-muhurta" />
          <SideItem to="/library" label="Library" Icon={BookOpen} collapsed={collapsed} testId="nav-library" />
          <SideItem to="/settings" label="Settings" Icon={Settings} collapsed={collapsed} testId="nav-settings" />
        </nav>

        <div className={`border-t border-[color:var(--jai-border)] ${collapsed ? "p-3 flex justify-center" : "p-5"}`}>
          {collapsed ? (
            <button
              onClick={signOut}
              className="w-9 h-9 rounded-md flex items-center justify-center text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-green-deep)] hover:bg-[color:var(--jai-surface)]"
              title="Sign out"
              data-testid="signout-btn"
            >
              <LogOut size={14} />
            </button>
          ) : (
            <>
              <div className="text-xs text-[color:var(--jai-text-muted)] mb-1">Signed in as</div>
              <div className="font-serif-display text-lg text-[color:var(--jai-parchment)] mb-3 truncate" data-testid="profile-name">{displayName}</div>
              <Button variant="ghost" size="sm" onClick={signOut} className="text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)] px-0" data-testid="signout-btn">
                <LogOut size={14} className="mr-2" /> Sign out
              </Button>
            </>
          )}
        </div>
      </aside>

      {/* Simple / Advanced — switches how much technical chart detail is
          shown across Dashboard, Chat and Muhurta (Shadbala, Ashtakavarga,
          dignity, yogas, the full Dasha tree, the "Why?" panel in Chat, the
          tomorrow view in Muhurta). Advanced mode ALSO unlocks the chart
          card download on Dashboard — that's intentional: this toggle is
          the actual gate for that feature, not a paid plan. It's a free,
          per-browser preference (localStorage), not tied to the account
          at all. */}
      <div className="fixed top-4 right-16 z-20" data-testid="display-mode-toggle-wrap">
        {showAdvancedHint && (
          <div
            className="absolute top-full right-0 mt-2 w-56 modal-surface p-3 text-xs text-[color:var(--jai-green-deep)] fade-up"
            role="status"
            data-testid="advanced-mode-hint"
          >
            <button
              onClick={dismissAdvancedHint}
              className="absolute top-1.5 right-1.5 text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)]"
              aria-label="Dismiss"
            >
              <X size={12} />
            </button>
            <strong className="block mb-1">Try Advanced →</strong>
            Unlocks Shadbala, Ashtakavarga, detected yogas, House Lords, full divisional charts,
            and your downloadable chart card.
          </div>
        )}
        <div
          className="flex items-center rounded-full border border-[color:var(--jai-border)] bg-[color:var(--jai-surface)] p-0.5 shadow-sm"
        >
        <button
          onClick={() => { setMode("simple"); dismissAdvancedHint(); }}
          className={`px-3 py-1.5 rounded-full text-[11px] uppercase tracking-widest font-semibold transition-colors ${
            mode === "simple"
              ? "bg-[color:var(--jai-green)] text-[color:var(--jai-surface)]"
              : "text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-green-deep)]"
          }`}
          title="Plain-language view — for everyday users"
          data-testid="display-mode-simple-btn"
        >
          Simple
        </button>
        <button
          onClick={() => { setMode("advanced"); dismissAdvancedHint(); }}
          className={`px-3 py-1.5 rounded-full text-[11px] uppercase tracking-widest font-semibold transition-colors ${
            mode === "advanced"
              ? "bg-[color:var(--jai-gold)] text-[color:var(--jai-surface)]"
              : "text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-green-deep)]"
          }`}
          title="Full technical chart data, plus your downloadable chart card"
          data-testid="display-mode-advanced-btn"
        >
          Advanced
        </button>
        </div>
      </div>

      <button
        onClick={toggleTheme}
        className="fixed top-4 right-4 z-20 w-10 h-10 rounded-full flex items-center justify-center bg-[color:var(--jai-surface)] border border-[color:var(--jai-border)] text-[color:var(--jai-gold)] hover:text-[color:var(--jai-gold-soft)] hover:border-[color:var(--jai-border-gold)] transition-colors shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--jai-green-deep)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--jai-bg)]"
        title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        data-testid="theme-toggle-btn"
      >
        {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
      </button>

      <main className="flex-1 relative z-[1] overflow-y-auto">{children}</main>

      {/* Rename dialog */}
      <AlertDialog open={!!renameTarget} onOpenChange={(v) => !v && setRenameTarget(null)}>
        <AlertDialogContent className="bg-[color:var(--jai-surface)] border-[color:var(--jai-border)]">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-serif-display text-[color:var(--jai-green-deep)]">Rename chat</AlertDialogTitle>
            <AlertDialogDescription className="text-[color:var(--jai-text-muted)]">Give this conversation a memorable name.</AlertDialogDescription>
          </AlertDialogHeader>
          <Input value={renameValue} onChange={(e) => setRenameValue(e.target.value)} data-testid="rename-input" onKeyDown={(e) => e.key === "Enter" && doRename()} />
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={doRename} className="bg-[color:var(--jai-green)] text-[color:var(--jai-surface)]" data-testid="rename-save">Save</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete dialog */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(v) => !v && setDeleteTarget(null)}>
        <AlertDialogContent className="bg-[color:var(--jai-surface)] border-[color:var(--jai-border)]">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-serif-display text-[color:var(--jai-green-deep)]">Delete this chat?</AlertDialogTitle>
            <AlertDialogDescription className="text-[color:var(--jai-text-muted)]">All messages in "{deleteTarget?.name}" will be permanently removed.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={doDelete} className="bg-red-700 text-white" data-testid="delete-confirm">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete project dialog */}
      <AlertDialog open={!!deleteProjectTarget} onOpenChange={(v) => !v && setDeleteProjectTarget(null)}>
        <AlertDialogContent className="bg-[color:var(--jai-surface)] border-[color:var(--jai-border)]">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-serif-display text-[color:var(--jai-green-deep)]">Delete "{deleteProjectTarget?.label}"?</AlertDialogTitle>
            <AlertDialogDescription className="text-[color:var(--jai-text-muted)]">
              The project itself will be removed, but its chats aren't deleted — they'll move back to your general Conversation list.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={doDeleteProject} className="bg-red-700 text-white" data-testid="delete-project-confirm">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function SideItem({ to, label, Icon, collapsed, testId }) {
  return (
    <NavLink
      to={to}
      data-testid={testId}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-lg transition-colors ${
          collapsed ? "px-2 py-3 justify-center" : "px-3 py-2.5"
        } ${
          isActive
            ? "bg-[color:var(--jai-surface-2)] text-[color:var(--jai-green-deep)] border border-[color:var(--jai-border)]"
            : "text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-text)] hover:bg-[color:var(--jai-surface)]/60"
        }`
      }
    >
      <Icon size={17} />
      {!collapsed && <span className="font-medium tracking-wide">{label}</span>}
    </NavLink>
  );
}
