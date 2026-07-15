import { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { format } from "date-fns";
import { toast } from "sonner";
import { CalendarIcon, MapPin, Loader2, User as UserIcon, Sparkles, Navigation, AlertTriangle } from "lucide-react";
import { useAuth, clearStoredToken } from "@/context/AuthContext";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TIMEZONES = [
  { label: "IST (India, +5:30)", value: 5.5 },
  { label: "GMT / UTC (0)", value: 0 },
  { label: "EST (US East, -5:00)", value: -5 },
  { label: "PST (US Pacific, -8:00)", value: -8 },
  { label: "CET (Central Europe, +1:00)", value: 1 },
  { label: "GST (Gulf, +4:00)", value: 4 },
  { label: "SGT (Singapore, +8:00)", value: 8 },
  { label: "AEST (Australia East, +10:00)", value: 10 },
];

function SectionCard({ icon: Icon, title, subtitle, children }) {
  return (
    <div className="card-surface p-6 sm:p-8 space-y-6">
      <div className="flex items-center gap-3">
        <Icon size={18} className="text-[color:var(--jai-gold)]" />
        <div>
          <div className="font-serif-display text-xl text-[color:var(--jai-green-deep)]">{title}</div>
          {subtitle && <div className="text-sm text-[color:var(--jai-text-muted)] mt-0.5">{subtitle}</div>}
        </div>
      </div>
      {children}
    </div>
  );
}

export default function Settings() {
  const navigate = useNavigate();
  const { user, setUser, logout } = useAuth();

  // Profile
  const [name, setName] = useState(user?.name || "");
  const [phone, setPhone] = useState(user?.phone || "");
  const [savingProfile, setSavingProfile] = useState(false);

  // Birth details
  const [birthLoaded, setBirthLoaded] = useState(false);
  const [birthName, setBirthName] = useState("");
  const [dob, setDob] = useState(null);
  const [tob, setTob] = useState("");
  const [tz, setTz] = useState(5.5);
  const [place, setPlace] = useState("");
  const [lat, setLat] = useState(null);
  const [lon, setLon] = useState(null);
  const [geocoding, setGeocoding] = useState(false);
  const [savingBirth, setSavingBirth] = useState(false);

  // Current location
  const [curPlace, setCurPlace] = useState(user?.current_place || "");
  const [curLat, setCurLat] = useState(user?.current_lat ?? null);
  const [curLon, setCurLon] = useState(user?.current_lon ?? null);
  const [curGeocoding, setCurGeocoding] = useState(false);
  const [savingLocation, setSavingLocation] = useState(false);

  // Danger zone
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get(`${API}/profile`);
        if (res.data) {
          setBirthName(res.data.name || "");
          setDob(res.data.dob ? new Date(res.data.dob + "T00:00:00") : null);
          setTob(res.data.tob || "");
          setTz(res.data.tz_offset ?? 5.5);
          setPlace(res.data.place || "");
          setLat(res.data.lat ?? null);
          setLon(res.data.lon ?? null);
        }
      } catch {
        // no profile yet — fields stay blank
      } finally {
        setBirthLoaded(true);
      }
    })();
  }, []);

  const saveProfile = async () => {
    setSavingProfile(true);
    try {
      const res = await axios.patch(`${API}/account`, { name: name.trim(), phone: phone.trim() });
      setUser(res.data);
      toast.success("Profile updated");
    } catch {
      toast.error("Could not update profile");
    } finally {
      setSavingProfile(false);
    }
  };

  const geocodeBirth = async () => {
    if (!place.trim()) return toast.error("Enter a place first");
    setGeocoding(true);
    try {
      const res = await axios.get(`${API}/geocode`, { params: { q: place } });
      if (res.data.results?.length) {
        const r = res.data.results[0];
        setLat(r.lat);
        setLon(r.lon);
        toast.success(`Found: ${r.place.split(",").slice(0, 3).join(",")}`);
      } else {
        toast.error("Place not found — try adding country/state");
      }
    } catch {
      toast.error("Geocoding failed");
    } finally {
      setGeocoding(false);
    }
  };

  const saveBirth = async () => {
    if (!birthName.trim() || !dob || !tob || !lat || !lon) {
      toast.error("Please fill all fields and confirm the birth place");
      return;
    }
    setSavingBirth(true);
    try {
      await axios.post(`${API}/profile`, {
        name: birthName, dob: format(dob, "yyyy-MM-dd"), tob, tz_offset: tz, lat, lon, place,
      });
      toast.success("Kundali updated");
    } catch {
      toast.error("Could not update birth details");
    } finally {
      setSavingBirth(false);
    }
  };

  const geocodeCurrent = async () => {
    if (!curPlace.trim()) return toast.error("Enter a place first");
    setCurGeocoding(true);
    try {
      const res = await axios.get(`${API}/geocode`, { params: { q: curPlace } });
      if (res.data.results?.length) {
        const r = res.data.results[0];
        setCurLat(r.lat);
        setCurLon(r.lon);
        toast.success(`Found: ${r.place.split(",").slice(0, 3).join(",")}`);
      } else {
        toast.error("Place not found — try adding country/state");
      }
    } catch {
      toast.error("Geocoding failed");
    } finally {
      setCurGeocoding(false);
    }
  };

  const saveLocation = async () => {
    if (!curLat || !curLon) {
      toast.error("Confirm your current location first");
      return;
    }
    setSavingLocation(true);
    try {
      const res = await axios.put(`${API}/account/location`, { lat: curLat, lon: curLon, place: curPlace });
      setUser(res.data);
      toast.success("Current location updated");
    } catch {
      toast.error("Could not update location");
    } finally {
      setSavingLocation(false);
    }
  };

  const signOut = async () => {
    await logout();
    navigate("/");
  };

  const canDelete = confirmText.trim() === "DELETE" || confirmText.trim().toLowerCase() === (user?.email || "").toLowerCase();

  const doDelete = async () => {
    setDeleting(true);
    try {
      await axios.delete(`${API}/account`);
      clearStoredToken();
      toast.success("Account deleted");
      navigate("/");
    } catch {
      toast.error("Could not delete account");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-12 space-y-8" data-testid="settings-page">
      <div>
        <div className="overline mb-2">Settings</div>
        <h1 className="font-serif-display text-4xl text-[color:var(--jai-green-deep)]">Your Compass</h1>
      </div>

      {/* Profile */}
      <SectionCard icon={UserIcon} title="Profile" subtitle="Your account details">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <div>
            <Label className="overline">Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-3 bg-transparent border-0 border-b border-[color:var(--jai-border)] rounded-none px-0 text-lg font-serif-display focus-visible:border-[color:var(--jai-gold)] focus-visible:ring-0"
              data-testid="settings-name"
            />
          </div>
          <div>
            <Label className="overline">Phone</Label>
            <Input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="Optional"
              className="mt-3 bg-transparent border-0 border-b border-[color:var(--jai-border)] rounded-none px-0 text-lg font-serif-display placeholder:text-[color:var(--jai-text-muted)]/60 focus-visible:border-[color:var(--jai-gold)] focus-visible:ring-0"
              data-testid="settings-phone"
            />
          </div>
        </div>
        <div>
          <Label className="overline">Email</Label>
          <div className="mt-3 text-lg font-serif-display text-[color:var(--jai-text-muted)]">{user?.email}</div>
        </div>
        <Button onClick={saveProfile} disabled={savingProfile} className="gold-btn" data-testid="settings-save-profile">
          {savingProfile ? <Loader2 size={14} className="mr-2 animate-spin" /> : null}
          Save Profile
        </Button>
      </SectionCard>

      {/* Birth Details */}
      {birthLoaded && (
        <SectionCard icon={Sparkles} title="Birth Details" subtitle="Edit the details behind your Kundali">
          <div>
            <Label className="overline">Name at Birth</Label>
            <Input
              value={birthName}
              onChange={(e) => setBirthName(e.target.value)}
              className="mt-3 bg-transparent border-0 border-b border-[color:var(--jai-border)] rounded-none px-0 text-lg font-serif-display focus-visible:border-[color:var(--jai-gold)] focus-visible:ring-0"
              data-testid="settings-birth-name"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <Label className="overline">Date of Birth</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="ghost"
                    className="mt-3 w-full justify-start px-0 border-0 border-b border-[color:var(--jai-border)] rounded-none text-lg font-serif-display text-left h-auto py-2 hover:bg-transparent"
                    data-testid="settings-dob"
                  >
                    <CalendarIcon size={16} className="mr-3 text-[color:var(--jai-gold)]" />
                    {dob ? format(dob, "PPP") : <span className="text-[color:var(--jai-text-muted)]/60">Pick a date</span>}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0 bg-[color:var(--jai-surface)] border-[color:var(--jai-border)]" align="start">
                  <Calendar mode="single" selected={dob} onSelect={setDob} captionLayout="dropdown-buttons" fromYear={1900} toYear={new Date().getFullYear()} initialFocus />
                </PopoverContent>
              </Popover>
            </div>
            <div>
              <Label className="overline">Time of Birth (24h)</Label>
              <Input
                type="time"
                value={tob}
                onChange={(e) => setTob(e.target.value)}
                className="mt-3 bg-transparent border-0 border-b border-[color:var(--jai-border)] rounded-none px-0 text-lg font-serif-display focus-visible:border-[color:var(--jai-gold)] focus-visible:ring-0"
                data-testid="settings-tob"
              />
            </div>
          </div>
          <div>
            <Label className="overline">Timezone at Birth</Label>
            <Select value={String(tz)} onValueChange={(v) => setTz(parseFloat(v))}>
              <SelectTrigger
                className="mt-3 bg-transparent border-0 border-b border-[color:var(--jai-border)] rounded-none px-0 text-lg font-serif-display focus:ring-0 focus:border-[color:var(--jai-gold)]"
                data-testid="settings-tz"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[color:var(--jai-surface)] border-[color:var(--jai-border)]">
                {TIMEZONES.map((t) => <SelectItem key={t.value} value={String(t.value)}>{t.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="overline">Place of Birth</Label>
            <div className="mt-3 flex items-end gap-3 border-b border-[color:var(--jai-border)] pb-1">
              <MapPin size={16} className="text-[color:var(--jai-gold)] mb-3" />
              <Input
                value={place}
                onChange={(e) => { setPlace(e.target.value); setLat(null); setLon(null); }}
                onKeyDown={(e) => e.key === "Enter" && geocodeBirth()}
                className="bg-transparent border-0 rounded-none px-0 text-lg font-serif-display focus-visible:ring-0"
                data-testid="settings-place"
              />
              <Button onClick={geocodeBirth} disabled={geocoding} size="sm" variant="ghost" className="text-[color:var(--jai-gold)] hover:text-[color:var(--jai-gold-soft)] hover:bg-transparent -mb-1" data-testid="settings-geocode-btn">
                {geocoding ? <Loader2 size={14} className="animate-spin" /> : "Locate"}
              </Button>
            </div>
            {lat !== null && (
              <div className="mt-2 text-xs text-[color:var(--jai-gold)]/80">{lat.toFixed(4)}°, {lon.toFixed(4)}° confirmed</div>
            )}
          </div>
          <Button onClick={saveBirth} disabled={savingBirth} className="gold-btn" data-testid="settings-save-birth">
            {savingBirth ? <Loader2 size={14} className="mr-2 animate-spin" /> : null}
            Recast my Kundali
          </Button>
        </SectionCard>
      )}

      {/* Current Location */}
      <SectionCard icon={Navigation} title="Current Location" subtitle="Used for accurate daily transits and Panchang — separate from your birth place">
        <div className="flex items-end gap-3 border-b border-[color:var(--jai-border)] pb-1">
          <MapPin size={16} className="text-[color:var(--jai-gold)] mb-3" />
          <Input
            value={curPlace}
            onChange={(e) => { setCurPlace(e.target.value); setCurLat(null); setCurLon(null); }}
            onKeyDown={(e) => e.key === "Enter" && geocodeCurrent()}
            placeholder="Where are you now?"
            className="bg-transparent border-0 rounded-none px-0 text-lg font-serif-display placeholder:text-[color:var(--jai-text-muted)]/60 focus-visible:ring-0"
            data-testid="settings-current-place"
          />
          <Button onClick={geocodeCurrent} disabled={curGeocoding} size="sm" variant="ghost" className="text-[color:var(--jai-gold)] hover:text-[color:var(--jai-gold-soft)] hover:bg-transparent -mb-1" data-testid="settings-current-geocode-btn">
            {curGeocoding ? <Loader2 size={14} className="animate-spin" /> : "Locate"}
          </Button>
        </div>
        {curLat !== null && (
          <div className="text-xs text-[color:var(--jai-gold)]/80">{curLat.toFixed(4)}°, {curLon.toFixed(4)}° confirmed</div>
        )}
        <Button onClick={saveLocation} disabled={savingLocation} className="gold-btn" data-testid="settings-save-location">
          {savingLocation ? <Loader2 size={14} className="mr-2 animate-spin" /> : null}
          Save Location
        </Button>
      </SectionCard>

      {/* Danger Zone */}
      <SectionCard icon={AlertTriangle} title="Danger Zone" subtitle="Careful — these actions are permanent">
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={signOut} data-testid="settings-signout-btn">Sign out</Button>
          <Button variant="outline" onClick={() => setDeleteOpen(true)} className="text-red-700 border-red-300 hover:bg-red-50" data-testid="settings-delete-btn">
            Delete Account
          </Button>
        </div>
      </SectionCard>

      <AlertDialog open={deleteOpen} onOpenChange={(v) => { setDeleteOpen(v); if (!v) setConfirmText(""); }}>
        <AlertDialogContent className="bg-[color:var(--jai-surface)] border-[color:var(--jai-border)]">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-serif-display text-[color:var(--jai-green-deep)]">Delete your account?</AlertDialogTitle>
            <AlertDialogDescription className="text-[color:var(--jai-text-muted)]">
              This permanently deletes your Kundali, all conversations, uploaded books, and account data. This cannot be undone.
              Type <strong>DELETE</strong> or your email ({user?.email}) to confirm.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Input
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="DELETE"
            data-testid="settings-delete-confirm-input"
          />
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={doDelete}
              disabled={!canDelete || deleting}
              className="bg-red-700 text-white"
              data-testid="settings-delete-confirm-btn"
            >
              {deleting ? <Loader2 size={14} className="mr-2 animate-spin" /> : null}
              Delete Forever
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
