import { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { format } from "date-fns";
import { toast } from "sonner";
import { CalendarIcon, MapPin, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

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

export default function Onboarding() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [name, setName] = useState(user?.name || "");
  const [dob, setDob] = useState(null);
  const [tob, setTob] = useState("");
  const [tz, setTz] = useState(5.5);
  const [place, setPlace] = useState("");
  const [lat, setLat] = useState(null);
  const [lon, setLon] = useState(null);
  const [geocoding, setGeocoding] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // If user already has a profile, redirect to dashboard
  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get(`${API}/profile`);
        if (res.data) navigate("/dashboard", { replace: true });
      } catch {}
    })();
  }, [navigate]);

  const geocode = async () => {
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
    } catch (e) {
      toast.error("Geocoding failed");
    } finally {
      setGeocoding(false);
    }
  };

  const submit = async () => {
    if (!name.trim() || !dob || !tob || !lat || !lon) {
      toast.error("Please fill all fields and confirm the birth place");
      return;
    }
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/profile`, {
        name, dob: format(dob, "yyyy-MM-dd"), tob, tz_offset: tz, lat, lon, place,
      });
      toast.success("Chart cast. Welcome, " + res.data.name);
      navigate("/dashboard");
    } catch (e) {
      toast.error("Could not save your chart");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center px-6 py-16" data-testid="onboarding-page">
      <div className="absolute inset-0 -z-10">
        <div
          className="absolute inset-0 opacity-25"
          style={{
            backgroundImage: "url(https://images.unsplash.com/photo-1648717008621-ee7e6acfe270?w=1920&q=80)",
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        />
        <div className="absolute inset-0 bg-[color:var(--jai-bg)]/80" />
      </div>

      <div className="relative w-full max-w-2xl">
        <div className="text-center mb-14 fade-up">
          <div className="overline mb-6">Sanatan · Jyotish · Personal Counsel</div>
          <h1 className="font-serif-display text-5xl sm:text-6xl lg:text-7xl leading-[0.95] text-[color:var(--jai-parchment)]">
            The <em className="text-[color:var(--jai-gold-soft)]">stars</em> await<br />
            your <em className="text-[color:var(--jai-gold-soft)]">arrival</em>.
          </h1>
          <p className="mt-6 text-[color:var(--jai-text-muted)] max-w-lg mx-auto text-base leading-relaxed">
            Share the moment you drew your first breath. The classical Shastras will speak of what has been, what is,
            and what must unfold.
          </p>
        </div>

        <div className="card-surface p-8 sm:p-10 space-y-6 fade-up delay-1">
          <div>
            <Label className="overline">Your Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Arjuna"
              className="mt-3 bg-transparent border-0 border-b border-[color:var(--jai-border)] rounded-none px-0 text-lg font-serif-display placeholder:text-[color:var(--jai-text-muted)]/60 focus-visible:border-[color:var(--jai-gold)] focus-visible:ring-0"
              data-testid="onboarding-name"
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
                    data-testid="onboarding-dob"
                  >
                    <CalendarIcon size={16} className="mr-3 text-[color:var(--jai-gold)]" />
                    {dob ? format(dob, "PPP") : <span className="text-[color:var(--jai-text-muted)]/60">Pick a date</span>}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0 bg-[color:var(--jai-surface)] border-[color:var(--jai-border)]" align="start">
                  <Calendar
                    mode="single"
                    selected={dob}
                    onSelect={setDob}
                    captionLayout="dropdown-buttons"
                    fromYear={1900}
                    toYear={new Date().getFullYear()}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
            </div>

            <div>
              <Label className="overline">Time of Birth (24h)</Label>
              <Input
                type="time"
                value={tob}
                onChange={(e) => setTob(e.target.value)}
                className="mt-3 bg-transparent border-0 border-b border-[color:var(--jai-border)] rounded-none px-0 text-lg font-serif-display placeholder:text-[color:var(--jai-text-muted)]/60 focus-visible:border-[color:var(--jai-gold)] focus-visible:ring-0"
                data-testid="onboarding-tob"
              />
            </div>
          </div>

          <div>
            <Label className="overline">Timezone at Birth</Label>
            <Select value={String(tz)} onValueChange={(v) => setTz(parseFloat(v))}>
              <SelectTrigger
                className="mt-3 bg-transparent border-0 border-b border-[color:var(--jai-border)] rounded-none px-0 text-lg font-serif-display focus:ring-0 focus:border-[color:var(--jai-gold)]"
                data-testid="onboarding-tz"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[color:var(--jai-surface)] border-[color:var(--jai-border)]">
                {TIMEZONES.map((t) => (
                  <SelectItem key={t.value} value={String(t.value)}>{t.label}</SelectItem>
                ))}
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
                onKeyDown={(e) => e.key === "Enter" && geocode()}
                placeholder="Varanasi, India"
                className="bg-transparent border-0 rounded-none px-0 text-lg font-serif-display placeholder:text-[color:var(--jai-text-muted)]/60 focus-visible:ring-0"
                data-testid="onboarding-place"
              />
              <Button
                onClick={geocode}
                disabled={geocoding}
                size="sm"
                variant="ghost"
                className="text-[color:var(--jai-gold)] hover:text-[color:var(--jai-gold-soft)] hover:bg-transparent -mb-1"
                data-testid="onboarding-geocode-btn"
              >
                {geocoding ? <Loader2 size={14} className="animate-spin" /> : "Locate"}
              </Button>
            </div>
            {lat !== null && (
              <div className="mt-2 text-xs text-[color:var(--jai-gold)]/80" data-testid="geocode-result">
                {lat.toFixed(4)}°, {lon.toFixed(4)}° confirmed
              </div>
            )}
          </div>

          <Button
            onClick={submit}
            disabled={submitting}
            className="gold-btn w-full h-14 mt-4 font-serif-display text-lg tracking-wide glow-hover"
            data-testid="onboarding-submit-btn"
          >
            {submitting ? <Loader2 size={16} className="mr-2 animate-spin" /> : null}
            Cast my Kundali
          </Button>
        </div>

        <p className="text-center text-xs text-[color:var(--jai-text-muted)] mt-10 tracking-wide fade-up delay-3">
          Compass Astro · Sidereal · Lahiri Ayanamsa · Powered by Claude Sonnet 4.5
        </p>
      </div>
    </div>
  );
}
