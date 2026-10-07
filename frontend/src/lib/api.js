import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, withCredentials: true });
// withCredentials WAJIB true -- supaya session cookie login (dari
// /api/auth/login) ikut terkirim di setiap request berikutnya.

export const STATUS_COLORS = {
  "Tidak Terlambat": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "Terlambat": "bg-amber-50 text-amber-700 border-amber-200",
  "Izin": "bg-blue-50 text-blue-700 border-blue-200",
  "Alpa": "bg-red-50 text-red-700 border-red-200",
};

export const STATUS_DOT = {
  "Tidak Terlambat": "bg-emerald-500",
  "Terlambat": "bg-amber-500",
  "Izin": "bg-blue-500",
  "Alpa": "bg-red-500",
};

export const BULAN_NAMES = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"];
