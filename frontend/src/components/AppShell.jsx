import { useState, useEffect } from "react";
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import {
  LayoutGrid,
  MessageSquare,
  BookOpen,
  Sparkles,
  LogOut,
  Menu,
  ChevronRight,
  ChevronDown,
  Plus,
  MoreHorizontal,
  Pencil,
  Trash2,
} from "lucide-react";
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

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AppShell({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("jyotish_sidebar_collapsed") === "1"
  );
  const [threadsOpen, setThreadsOpen] = useState(true);
  const [threads, setThreads] = useState([]);
  const [renameTarget, setRenameTarget] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(null);

  const name = localStorage.getItem("jyotish_profile_name") || "Seeker";
  const profileId = localStorage.getItem("jyotish_profile_id");
  const activeThread = new URLSearchParams(location.search).get("t");

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("jyotish_sidebar_collapsed", next ? "1" : "0");
  };

  const loadThreads = async () => {
    if (!profileId) return;
    try {
      const res = await axios.get(`${API}/threads`, { params: { profile_id: profileId } });
      setThreads(res.data.threads || []);
    } catch (e) {
      // silent
    }
  };

  useEffect(() => {
    loadThreads();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId]);

  const createThread = async () => {
    try {
      const res = await axios.post(`${API}/threads`, { profile_id: profileId, name: `Chat ${threads.length + 1}` });
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
    toast.success("Renamed");
  };

  const doDelete = async () => {
    if (!deleteTarget) return;
    await axios.delete(`${API}/threads/${deleteTarget.id}`);
    if (activeThread === deleteTarget.id) navigate(`/chat`);
    setDeleteTarget(null);
    loadThreads();
    toast.success("Chat deleted");
  };

  const signOut = () => {
    localStorage.removeItem("jyotish_profile_id");
    localStorage.removeItem("jyotish_profile_name");
    navigate("/onboarding");
  };

  const nav = [
    { to: "/dashboard", label: "Kundali", Icon: LayoutGrid, testId: "nav-dashboard" },
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
            <div className="flex-1 min-w-0">
              <div className="font-serif-display text-xl leading-none text-[color:var(--jai-green-deep)]">Jyotish AI</div>
              <div className="overline mt-1">Vedic Counsel</div>
            </div>
          )}
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {/* Dashboard */}
          <SideItem to="/dashboard" label="Kundali" Icon={LayoutGrid} collapsed={collapsed} testId="nav-dashboard" />

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
                {threads.map((t) => (
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

          <SideItem to="/library" label="Library" Icon={BookOpen} collapsed={collapsed} testId="nav-library" />
        </nav>

        <div className={`border-t border-[color:var(--jai-border)] ${collapsed ? "p-3 flex justify-center" : "p-5"}`}>
          {collapsed ? (
            <button
              onClick={signOut}
              className="w-9 h-9 rounded-md flex items-center justify-center text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-green-deep)] hover:bg-[color:var(--jai-surface)]"
              title="Reset chart"
              data-testid="signout-btn"
            >
              <LogOut size={14} />
            </button>
          ) : (
            <>
              <div className="text-xs text-[color:var(--jai-text-muted)] mb-1">Signed in as</div>
              <div className="font-serif-display text-lg text-[color:var(--jai-parchment)] mb-3 truncate" data-testid="profile-name">{name}</div>
              <Button variant="ghost" size="sm" onClick={signOut} className="text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)] px-0" data-testid="signout-btn">
                <LogOut size={14} className="mr-2" /> Reset chart
              </Button>
            </>
          )}
        </div>
      </aside>

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
