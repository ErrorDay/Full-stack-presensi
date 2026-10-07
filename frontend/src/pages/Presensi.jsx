import { useEffect, useRef, useState, useCallback } from "react";
import { api, API, STATUS_COLORS, BULAN_NAMES } from "@/lib/api";
import { toast } from "sonner";
import { Camera, CameraOff, ScanFace, Download, FileDown, BookOpen, ClipboardCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const STATUSES = ["Tidak Terlambat", "Terlambat", "Izin", "Alpa"];
const today = () => new Date().toISOString().slice(0, 10);

export default function Presensi() {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState(null);
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [simStudent, setSimStudent] = useState("");

  const [harian, setHarian] = useState({ date: today(), year: "", jam: "", class_id: "all", status: "all" });
  const [harianRows, setHarianRows] = useState([]);
  const [bulanan, setBulanan] = useState({ month: new Date().getMonth() + 1, year: new Date().getFullYear(), class_id: "all" });
  const [bulananData, setBulananData] = useState(null);
  const [mode, setMode] = useState("presensi"); // presensi | perpustakaan
  const [libPekan, setLibPekan] = useState({ date: today(), class_id: "all" });
  const [libPekanData, setLibPekanData] = useState(null);
  const [libBulanan, setLibBulanan] = useState({ month: new Date().getMonth() + 1, year: new Date().getFullYear(), class_id: "all" });
  const [libBulananData, setLibBulananData] = useState(null);

  const loadHarian = useCallback(async () => {
    const params = { date: harian.date };
    if (harian.year) params.year = harian.year;
    if (harian.jam) params.jam = harian.jam;
    if (harian.class_id !== "all") params.class_id = harian.class_id;
    if (harian.status !== "all") params.status = harian.status;
    const r = await api.get("/attendance", { params });
    setHarianRows(r.data);
  }, [harian]);

  const loadBulanan = useCallback(async () => {
    const params = { month: bulanan.month, year: bulanan.year };
    if (bulanan.class_id !== "all") params.class_id = bulanan.class_id;
    const r = await api.get("/attendance/recap/monthly", { params });
    setBulananData(r.data);
  }, [bulanan]);

  useEffect(() => {
    api.get("/classes").then((r) => setClasses(r.data)).catch(() => {});
    api.get("/students").then((r) => setStudents(r.data)).catch(() => {});
  }, []);

  useEffect(() => { loadHarian().catch(() => {}); }, [loadHarian]);
  useEffect(() => { loadBulanan().catch(() => {}); }, [loadBulanan]);

  const loadLibPekan = useCallback(async () => {
    const params = { type: "weekly", date: libPekan.date };
    if (libPekan.class_id !== "all") params.class_id = libPekan.class_id;
    const r = await api.get("/library/recap", { params });
    setLibPekanData(r.data);
  }, [libPekan]);

  const loadLibBulanan = useCallback(async () => {
    const params = { type: "monthly", month: libBulanan.month, year: libBulanan.year };
    if (libBulanan.class_id !== "all") params.class_id = libBulanan.class_id;
    const r = await api.get("/library/recap", { params });
    setLibBulananData(r.data);
  }, [libBulanan]);

  useEffect(() => { if (mode === "perpustakaan") loadLibPekan().catch(() => {}); }, [mode, loadLibPekan]);
  useEffect(() => { if (mode === "perpustakaan") loadLibBulanan().catch(() => {}); }, [mode, loadLibBulanan]);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCameraOn(true);
    } catch {
      toast.error("Kamera tidak dapat diakses. Izinkan akses kamera di browser.");
    }
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCameraOn(false);
  };

  const showResult = (payload, recognized, message) => {
    if (recognized && payload) {
      setResult({ ok: true, ...payload });
      toast.success(payload.visit_ke
        ? `Kunjungan tercatat: ${payload.name} (kunjungan ke-${payload.visit_ke} hari ini)`
        : `Presensi berhasil: ${payload.name} · ${payload.status}`);
    } else {
      setResult({ ok: false, message: message || "Wajah tidak dikenali." });
      toast.error(message || "Wajah tidak dikenali");
    }
    if (mode === "perpustakaan") { loadLibPekan(); loadLibBulanan(); } else { loadHarian(); }
  };

  const scanFace = async () => {
    if (!videoRef.current || !cameraOn) return;
    if (scanning) return; // cegah request numpuk kalau scan sebelumnya belum selesai (penting untuk auto-scan loop)
    setScanning(true);
    setResult(null);
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    canvas.getContext("2d").drawImage(videoRef.current, 0, 0);
    const image = canvas.toDataURL("image/jpeg", 0.7).split(",")[1];
    try {
      const r = await api.post("/attendance/recognize", { image_base64: image, target: mode === "perpustakaan" ? "library" : "attendance" });
      showResult(r.data.record || r.data.visit, r.data.recognized, r.data.message);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Pemindaian gagal");
    } finally {
      setScanning(false);
    }
  };

  // --- AUTO-SCAN: selama kamera aktif, scanFace() dipanggil otomatis
  // secara berkala (tiap AUTO_SCAN_INTERVAL_MS), berlaku untuk KEDUA
  // mode (Presensi Kehadiran maupun Kunjungan Perpustakaan) karena
  // scanFace() sendiri sudah membaca `mode` saat ini untuk menentukan
  // target ("attendance"/"library"). Tombol "Pindai Wajah" manual
  // tetap ada untuk trigger ulang kalau auto-scan gagal mendeteksi.
  const AUTO_SCAN_INTERVAL_MS = 2000;
  const scanFaceRef = useRef(scanFace);
  useEffect(() => { scanFaceRef.current = scanFace; });

  useEffect(() => {
    if (!cameraOn) return;
    const id = setInterval(() => { scanFaceRef.current(); }, AUTO_SCAN_INTERVAL_MS);
    return () => clearInterval(id);
  }, [cameraOn]);

  const simulate = async () => {
    if (!simStudent) return;
    setScanning(true);
    setResult(null);
    try {
      const r = await api.post("/attendance/recognize", { student_id: simStudent, target: mode === "perpustakaan" ? "library" : "attendance" });
      showResult(r.data.record || r.data.visit, true);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Simulasi gagal");
    } finally {
      setScanning(false);
    }
  };

  const exportUrl = (path, params) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v && v !== "all")).toString();
    window.open(`${API}${path}?${qs}`, "_blank");
  };

  return (
    <div className="space-y-8" data-testid="presensi-page">
      <div>
        <h1 className="text-3xl font-bold text-[#111827]">Presensi</h1>
        <p className="text-sm text-[#6B7280] mt-1">Absensi dengan kamera & Face Recognition, serta rekap kehadiran</p>
      </div>

      <div className="grid grid-cols-2 gap-2 p-1.5 bg-white border border-[#E5E7EB] rounded-xl w-fit shadow-sm" data-testid="mode-toggle">
        <button data-testid="mode-presensi" onClick={() => { setMode("presensi"); setResult(null); }}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${mode === "presensi" ? "bg-[#1D4ED8] text-white" : "text-[#6B7280] hover:bg-[#F3F4F6]"}`}>
          <ClipboardCheck className="w-4 h-4" /> Presensi Kehadiran
        </button>
        <button data-testid="mode-perpustakaan" onClick={() => { setMode("perpustakaan"); setResult(null); }}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${mode === "perpustakaan" ? "bg-[#1D4ED8] text-white" : "text-[#6B7280] hover:bg-[#F3F4F6]"}`}>
          <BookOpen className="w-4 h-4" /> Kunjungan Perpustakaan
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white border border-[#E5E7EB] rounded-xl shadow-sm p-6" data-testid="camera-panel">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-[#111827]">{mode === "perpustakaan" ? "Kamera Kunjungan Perpustakaan" : "Kamera Presensi"}</h2>
            {cameraOn ? (
              <Button data-testid="camera-stop-btn" variant="outline" size="sm" onClick={stopCamera}><CameraOff className="w-4 h-4 mr-2" /> Matikan</Button>
            ) : (
              <Button data-testid="camera-start-btn" size="sm" onClick={startCamera} className="bg-[#1D4ED8] hover:bg-[#1E40AF]"><Camera className="w-4 h-4 mr-2" /> Aktifkan Kamera</Button>
            )}
          </div>

          <div className="relative aspect-video bg-[#0B1220] rounded-xl overflow-hidden">
            <video ref={videoRef} autoPlay playsInline muted className={`w-full h-full object-cover ${cameraOn ? "" : "hidden"}`} data-testid="camera-video" />
            {!cameraOn && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-6">
                <ScanFace className="w-12 h-12 text-[#3B82F6] mb-4" />
                <p className="text-sm text-gray-300 font-medium">Kamera belum aktif</p>
                <p className="text-xs text-gray-500 mt-1 max-w-sm">Aktifkan kamera untuk memulai presensi. Modul Face Recognition Python dapat dihubungkan melalui endpoint <span className="font-mono">POST /api/attendance/recognize</span>.</p>
              </div>
            )}
            {cameraOn && (
              <>
                <div className="absolute top-4 left-4 w-8 h-8 border-t-2 border-l-2 border-[#3B82F6] rounded-tl-md" />
                <div className="absolute top-4 right-4 w-8 h-8 border-t-2 border-r-2 border-[#3B82F6] rounded-tr-md" />
                <div className="absolute bottom-4 left-4 w-8 h-8 border-b-2 border-l-2 border-[#3B82F6] rounded-bl-md" />
                <div className="absolute bottom-4 right-4 w-8 h-8 border-b-2 border-r-2 border-[#3B82F6] rounded-br-md" />
                {scanning && <div className="scan-line absolute left-6 right-6 h-0.5 bg-[#3B82F6] shadow-[0_0_12px_#3B82F6]" />}
                <div className={`absolute inset-x-0 bottom-0 py-2 text-center text-xs font-mono ${result ? (result.ok ? "bg-emerald-600/90 text-white" : "bg-red-600/90 text-white") : "bg-black/50 text-gray-300"}`} data-testid="scan-status">
                  {result ? (result.ok ? `${result.name} · ${result.class_name || "Tanpa kelas"} · ${result.time} · ${result.visit_ke ? `Kunjungan ke-${result.visit_ke}` : result.status}` : result.message) : (scanning ? "Memindai wajah..." : "Siap memindai")}
                </div>
              </>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3 mt-5">
            <Button data-testid="scan-face-btn" onClick={scanFace} disabled={!cameraOn || scanning} className="bg-[#1D4ED8] hover:bg-[#1E40AF]">
              <ScanFace className="w-4 h-4 mr-2" /> {scanning ? "Memindai..." : "Pindai Wajah"}
            </Button>
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-xs text-[#6B7280]">Mode simulasi:</span>
              <Select value={simStudent} onValueChange={setSimStudent}>
                <SelectTrigger data-testid="sim-student-select" className="w-56 h-9"><SelectValue placeholder="Pilih siswa" /></SelectTrigger>
                <SelectContent>
                  {students.map((s) => <SelectItem key={s.id} value={s.id}>{s.name} · {s.class_name}</SelectItem>)}
                </SelectContent>
              </Select>
              <Button data-testid="simulate-btn" variant="outline" size="sm" onClick={simulate} disabled={!simStudent || scanning}>Catat Presensi</Button>
            </div>
          </div>
        </div>

        <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm p-6" data-testid="scan-result-panel">
          <h2 className="text-lg font-semibold text-[#111827] mb-4">Hasil Pemindaian</h2>
          {!result && <p className="text-sm text-[#6B7280]">Belum ada pemindaian. Hasil pengenalan wajah akan tampil di sini.</p>}
          {result && result.ok && (
            <div className="space-y-3">
              <div className="w-12 h-12 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                <ScanFace className="w-6 h-6 text-emerald-600" />
              </div>
              <div className="space-y-2 text-sm">
                <Row k="Nama" v={result.name} />
                <Row k="NIS/NISN" v={result.nisn} mono />
                <Row k="Kelas" v={result.class_name} />
                <Row k="Tanggal" v={result.date} mono />
                <Row k="Waktu" v={result.time} mono />
              </div>
              {result.visit_ke ? (
                <span data-testid="scan-result-status" className="inline-block text-xs px-3 py-1.5 rounded-full border font-medium bg-blue-50 text-blue-700 border-blue-200">Kunjungan ke-{result.visit_ke} hari ini</span>
              ) : (
                <span data-testid="scan-result-status" className={`inline-block text-xs px-3 py-1.5 rounded-full border font-medium ${STATUS_COLORS[result.status]}`}>{result.status}</span>
              )}
            </div>
          )}
          {result && !result.ok && (
            <div className="space-y-3">
              <div className="w-12 h-12 rounded-full bg-red-50 border border-red-200 flex items-center justify-center">
                <ScanFace className="w-6 h-6 text-red-500" />
              </div>
              <p className="text-sm text-[#111827] font-medium">Siswa tidak ditemukan</p>
              <p className="text-xs text-[#6B7280]">{result.message}</p>
            </div>
          )}
        </div>
      </div>

      {mode === "presensi" ? (
      <Tabs key="presensi" defaultValue="harian" data-testid="rekap-tabs">
        <TabsList>
          <TabsTrigger value="harian" data-testid="tab-rekap-harian">Rekap Harian</TabsTrigger>
          <TabsTrigger value="bulanan" data-testid="tab-rekap-bulanan">Rekap Bulanan</TabsTrigger>
        </TabsList>

        <TabsContent value="harian">
          <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm" data-testid="rekap-harian">
            <div className="flex flex-wrap items-end gap-4 px-6 py-5 border-b border-[#E5E7EB]">
              <div>
                <Label className="text-xs">Tanggal</Label>
                <Input data-testid="filter-tanggal" type="date" className="mt-1.5 w-44" value={harian.date}
                  onChange={(e) => setHarian((p) => ({ ...p, date: e.target.value }))} />
              </div>
              <div>
                <Label className="text-xs">Tahun</Label>
                <Input data-testid="filter-tahun" type="number" placeholder="cth: 2026" className="mt-1.5 w-28" value={harian.year}
                  onChange={(e) => setHarian((p) => ({ ...p, year: e.target.value }))} />
              </div>
              <div>
                <Label className="text-xs">Jam</Label>
                <Select value={harian.jam || "all"} onValueChange={(v) => setHarian((p) => ({ ...p, jam: v === "all" ? "" : v }))}>
                  <SelectTrigger data-testid="filter-jam" className="mt-1.5 w-32"><SelectValue placeholder="Semua" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Semua</SelectItem>
                    {["05", "06", "07", "08", "09", "10", "11", "12"].map((h) => <SelectItem key={h} value={h}>{h}:00</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Kelas</Label>
                <Select value={harian.class_id} onValueChange={(v) => setHarian((p) => ({ ...p, class_id: v }))}>
                  <SelectTrigger data-testid="filter-kelas-harian" className="mt-1.5 w-40"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Semua Kelas</SelectItem>
                    {classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Status</Label>
                <Select value={harian.status} onValueChange={(v) => setHarian((p) => ({ ...p, status: v }))}>
                  <SelectTrigger data-testid="filter-status" className="mt-1.5 w-44"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Semua Status</SelectItem>
                    {STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="ml-auto flex gap-2">
                <Button data-testid="export-harian-csv" variant="outline" size="sm"
                  onClick={() => exportUrl("/export/daily.csv", { date: harian.date, class_id: harian.class_id, status: harian.status })}>
                  <Download className="w-4 h-4 mr-2" /> CSV
                </Button>
                <Button data-testid="export-harian-pdf" variant="outline" size="sm"
                  onClick={() => exportUrl("/export/daily.pdf", { date: harian.date, class_id: harian.class_id, status: harian.status })}>
                  <FileDown className="w-4 h-4 mr-2" /> PDF
                </Button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="rekap-harian-table">
                <thead>
                  <tr className="text-left text-xs text-[#6B7280] border-b border-[#E5E7EB] bg-[#F9FAFB] sticky top-0">
                    <th className="px-6 py-3 font-medium">Nama</th>
                    <th className="px-6 py-3 font-medium">NIS/NISN</th>
                    <th className="px-6 py-3 font-medium">Kelas</th>
                    <th className="px-6 py-3 font-medium">Tanggal</th>
                    <th className="px-6 py-3 font-medium">Jam</th>
                    <th className="px-6 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {harianRows.map((r) => (
                    <tr key={r.id} className="border-b border-[#F3F4F6] last:border-0 hover:bg-[#F9FAFB]">
                      <td className="px-6 py-3 font-medium text-[#111827]">{r.name}</td>
                      <td className="px-6 py-3 font-mono text-xs">{r.nisn}</td>
                      <td className="px-6 py-3 text-[#6B7280]">{r.class_name}</td>
                      <td className="px-6 py-3 font-mono text-xs">{r.date}</td>
                      <td className="px-6 py-3 font-mono text-xs">{r.time}</td>
                      <td className="px-6 py-3"><span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${STATUS_COLORS[r.status]}`}>{r.status}</span></td>
                    </tr>
                  ))}
                  {harianRows.length === 0 && (
                    <tr><td colSpan={6} className="px-6 py-10 text-center text-sm text-[#6B7280]">Tidak ada data presensi untuk filter ini.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="bulanan">
          <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm" data-testid="rekap-bulanan">
            <div className="flex flex-wrap items-end gap-4 px-6 py-5 border-b border-[#E5E7EB]">
              <div>
                <Label className="text-xs">Bulan</Label>
                <Select value={String(bulanan.month)} onValueChange={(v) => setBulanan((p) => ({ ...p, month: Number(v) }))}>
                  <SelectTrigger data-testid="filter-bulan" className="mt-1.5 w-40"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {BULAN_NAMES.map((b, i) => <SelectItem key={i} value={String(i + 1)}>{b}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Tahun</Label>
                <Input data-testid="filter-tahun-bulanan" type="number" className="mt-1.5 w-28" value={bulanan.year}
                  onChange={(e) => setBulanan((p) => ({ ...p, year: Number(e.target.value) || p.year }))} />
              </div>
              <div>
                <Label className="text-xs">Kelas</Label>
                <Select value={bulanan.class_id} onValueChange={(v) => setBulanan((p) => ({ ...p, class_id: v }))}>
                  <SelectTrigger data-testid="filter-kelas-bulanan" className="mt-1.5 w-40"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Semua Kelas</SelectItem>
                    {classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              {bulananData && (
                <p className="text-xs text-[#6B7280] pb-2">Hari sekolah periode ini: <span className="font-mono font-semibold text-[#111827]">{bulananData.hari_sekolah}</span> hari (Sabtu, Minggu & hari libur tidak dihitung)</p>
              )}
              <div className="ml-auto flex gap-2">
                <Button data-testid="export-bulanan-csv" variant="outline" size="sm"
                  onClick={() => exportUrl("/export/monthly.csv", { month: bulanan.month, year: bulanan.year, class_id: bulanan.class_id })}>
                  <Download className="w-4 h-4 mr-2" /> CSV
                </Button>
                <Button data-testid="export-bulanan-pdf" variant="outline" size="sm"
                  onClick={() => exportUrl("/export/monthly.pdf", { month: bulanan.month, year: bulanan.year, class_id: bulanan.class_id })}>
                  <FileDown className="w-4 h-4 mr-2" /> PDF
                </Button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="rekap-bulanan-table">
                <thead>
                  <tr className="text-left text-xs text-[#6B7280] border-b border-[#E5E7EB] bg-[#F9FAFB]">
                    <th className="px-6 py-3 font-medium">Nama</th>
                    <th className="px-6 py-3 font-medium">Kelas</th>
                    <th className="px-6 py-3 font-medium text-right">Hadir</th>
                    <th className="px-6 py-3 font-medium text-right">Terlambat</th>
                    <th className="px-6 py-3 font-medium text-right">Izin</th>
                    <th className="px-6 py-3 font-medium text-right">Alpa</th>
                    <th className="px-6 py-3 font-medium text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {(bulananData?.rows || []).map((r) => (
                    <tr key={r.student_id} className="border-b border-[#F3F4F6] last:border-0 hover:bg-[#F9FAFB]">
                      <td className="px-6 py-3 font-medium text-[#111827]">{r.name}</td>
                      <td className="px-6 py-3 text-[#6B7280]">{r.class_name}</td>
                      <td className="px-6 py-3 text-right font-mono text-emerald-700">{r.hadir}</td>
                      <td className="px-6 py-3 text-right font-mono text-amber-700">{r.terlambat}</td>
                      <td className="px-6 py-3 text-right font-mono text-blue-700">{r.izin}</td>
                      <td className="px-6 py-3 text-right font-mono text-red-700">{r.alpa}</td>
                      <td className="px-6 py-3 text-right font-mono text-[#111827]">{r.total}</td>
                    </tr>
                  ))}
                  {bulananData && bulananData.rows.length === 0 && (
                    <tr><td colSpan={7} className="px-6 py-10 text-center text-sm text-[#6B7280]">Tidak ada data untuk periode ini.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </TabsContent>
      </Tabs>
      ) : (
      <Tabs key="perpustakaan" defaultValue="pekan" data-testid="rekap-perpustakaan-tabs">
        <TabsList>
          <TabsTrigger value="pekan" data-testid="tab-rekap-pekan">Rekap Pekan</TabsTrigger>
          <TabsTrigger value="bulanan" data-testid="tab-rekap-perpus-bulanan">Rekap Bulanan</TabsTrigger>
        </TabsList>

        <TabsContent value="pekan">
          <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm" data-testid="rekap-pekan">
            <div className="flex flex-wrap items-end gap-4 px-6 py-5 border-b border-[#E5E7EB]">
              <div>
                <Label className="text-xs">Tanggal dalam Pekan</Label>
                <Input data-testid="filter-pekan-tanggal" type="date" className="mt-1.5 w-44" value={libPekan.date}
                  onChange={(e) => setLibPekan((p) => ({ ...p, date: e.target.value }))} />
              </div>
              <div>
                <Label className="text-xs">Kelas</Label>
                <Select value={libPekan.class_id} onValueChange={(v) => setLibPekan((p) => ({ ...p, class_id: v }))}>
                  <SelectTrigger data-testid="filter-kelas-pekan" className="mt-1.5 w-40"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Semua Kelas</SelectItem>
                    {classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              {libPekanData && (
                <p className="text-xs text-[#6B7280] pb-2">Periode: <span className="font-mono font-medium text-[#111827]">{libPekanData.start}</span> s.d. <span className="font-mono font-medium text-[#111827]">{libPekanData.end}</span> (Senin–Minggu)</p>
              )}
              <div className="ml-auto flex gap-2">
                <Button data-testid="export-pekan-csv" variant="outline" size="sm"
                  onClick={() => exportUrl("/export/library.csv", { type: "weekly", date: libPekan.date, class_id: libPekan.class_id })}>
                  <Download className="w-4 h-4 mr-2" /> CSV
                </Button>
                <Button data-testid="export-pekan-pdf" variant="outline" size="sm"
                  onClick={() => exportUrl("/export/library.pdf", { type: "weekly", date: libPekan.date, class_id: libPekan.class_id })}>
                  <FileDown className="w-4 h-4 mr-2" /> PDF
                </Button>
              </div>
            </div>
            <LibSummary data={libPekanData} prefix="pekan" />
            {libPekanData && (
              <div className="flex flex-wrap gap-2 px-6 pt-4">
                {libPekanData.daily.map((d) => (
                  <div key={d.date} className="text-center bg-[#F9FAFB] border border-[#E5E7EB] rounded-lg px-3 py-2">
                    <p className="text-[10px] text-[#6B7280] font-mono">{d.date.slice(5)}</p>
                    <p className="text-sm font-mono font-semibold text-[#111827]">{d.visitors}</p>
                    <p className="text-[10px] text-[#6B7280]">pengunjung</p>
                  </div>
                ))}
              </div>
            )}
            <LibTable data={libPekanData} testid="rekap-pekan-table" />
          </div>
        </TabsContent>

        <TabsContent value="bulanan">
          <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm" data-testid="rekap-perpus-bulanan">
            <div className="flex flex-wrap items-end gap-4 px-6 py-5 border-b border-[#E5E7EB]">
              <div>
                <Label className="text-xs">Bulan</Label>
                <Select value={String(libBulanan.month)} onValueChange={(v) => setLibBulanan((p) => ({ ...p, month: Number(v) }))}>
                  <SelectTrigger data-testid="filter-bulan-perpus" className="mt-1.5 w-40"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {BULAN_NAMES.map((b, i) => <SelectItem key={i} value={String(i + 1)}>{b}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Tahun</Label>
                <Input data-testid="filter-tahun-perpus" type="number" className="mt-1.5 w-28" value={libBulanan.year}
                  onChange={(e) => setLibBulanan((p) => ({ ...p, year: Number(e.target.value) || p.year }))} />
              </div>
              <div>
                <Label className="text-xs">Kelas</Label>
                <Select value={libBulanan.class_id} onValueChange={(v) => setLibBulanan((p) => ({ ...p, class_id: v }))}>
                  <SelectTrigger data-testid="filter-kelas-perpus-bulanan" className="mt-1.5 w-40"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Semua Kelas</SelectItem>
                    {classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="ml-auto flex gap-2">
                <Button data-testid="export-perpus-bulanan-csv" variant="outline" size="sm"
                  onClick={() => exportUrl("/export/library.csv", { type: "monthly", month: libBulanan.month, year: libBulanan.year, class_id: libBulanan.class_id })}>
                  <Download className="w-4 h-4 mr-2" /> CSV
                </Button>
                <Button data-testid="export-perpus-bulanan-pdf" variant="outline" size="sm"
                  onClick={() => exportUrl("/export/library.pdf", { type: "monthly", month: libBulanan.month, year: libBulanan.year, class_id: libBulanan.class_id })}>
                  <FileDown className="w-4 h-4 mr-2" /> PDF
                </Button>
              </div>
            </div>
            <LibSummary data={libBulananData} prefix="bulanan" />
            <LibTable data={libBulananData} testid="rekap-perpus-bulanan-table" />
          </div>
        </TabsContent>
      </Tabs>
      )}
    </div>
  );
}

function Row({ k, v, mono }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-[#6B7280] text-xs">{k}</span>
      <span className={`text-[#111827] font-medium ${mono ? "font-mono text-xs" : ""}`}>{v}</span>
    </div>
  );
}

function LibSummary({ data, prefix }) {
  if (!data) return null;
  return (
    <div className="flex flex-wrap gap-3 px-6 pt-4" data-testid={`lib-summary-${prefix}`}>
      <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-2.5">
        <p className="text-xs text-blue-700">Total Kunjungan</p>
        <p className="text-xl font-mono font-bold text-blue-800">{data.total_visits}</p>
      </div>
      <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-2.5">
        <p className="text-xs text-emerald-700">Pengunjung Unik</p>
        <p className="text-xl font-mono font-bold text-emerald-800">{data.unique_students}</p>
      </div>
    </div>
  );
}

function LibTable({ data, testid }) {
  return (
    <div className="overflow-x-auto pt-4">
      <table className="w-full text-sm" data-testid={testid}>
        <thead>
          <tr className="text-left text-xs text-[#6B7280] border-b border-[#E5E7EB] bg-[#F9FAFB]">
            <th className="px-6 py-3 font-medium">Nama</th>
            <th className="px-6 py-3 font-medium">NIS/NISN</th>
            <th className="px-6 py-3 font-medium">Kelas</th>
            <th className="px-6 py-3 font-medium text-right">Jumlah Kunjungan</th>
            <th className="px-6 py-3 font-medium text-right">Hari Berbeda</th>
          </tr>
        </thead>
        <tbody>
          {(data?.rows || []).map((r) => (
            <tr key={r.student_id} className="border-b border-[#F3F4F6] last:border-0 hover:bg-[#F9FAFB]">
              <td className="px-6 py-3 font-medium text-[#111827]">{r.name}</td>
              <td className="px-6 py-3 font-mono text-xs">{r.nisn}</td>
              <td className="px-6 py-3 text-[#6B7280]">{r.class_name || "-"}</td>
              <td className="px-6 py-3 text-right font-mono text-[#1D4ED8] font-semibold">{r.visits}</td>
              <td className="px-6 py-3 text-right font-mono">{r.days}</td>
            </tr>
          ))}
          {(!data || data.rows.length === 0) && (
            <tr><td colSpan={5} className="px-6 py-10 text-center text-sm text-[#6B7280]">Belum ada kunjungan pada periode ini.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
