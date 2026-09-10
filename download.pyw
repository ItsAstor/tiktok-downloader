import io
import os
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from urllib.parse import urljoin
from PIL import Image, ImageTk
import requests

# --- Palette Setup ---
BG_DARK = "#121212"
BG_CARD = "#1e1e1e"
ACCENT_CYAN = "#00f2fe"
ACCENT_PINK = "#fe2c55"
TEXT_WHITE = "#ffffff"
TEXT_MUTED = "#a0a0a0"
BORDER_GRAY = "#2a2a2a"

class TikTokDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TikTok Downloader Pro")
        self.root.geometry("620x680")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_DARK)

        self.download_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        self.status_text = tk.StringVar(value="Ready • Listening to clipboard")
        self.is_downloading = False
        self.current_video_data = None
        self.last_clipboard = ""
        self.thumb_photo = None  # Reference to prevent garbage collection

        self._apply_styles()
        self._build_ui()
        self._setup_clipboard_listener()

    def _apply_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Dark styled progress bar
        style.configure(
            "Cyan.Horizontal.TProgressbar",
            troughcolor=BG_CARD,
            bordercolor=BORDER_GRAY,
            background=ACCENT_CYAN,
            lightcolor=ACCENT_CYAN,
            darkcolor=ACCENT_CYAN
        )

    def _build_ui(self):
        # Header
        header_frame = tk.Frame(self.root, bg=BG_DARK)
        header_frame.pack(fill="x", padx=24, pady=(20, 10))

        title_lbl = tk.Label(
            header_frame, text="TikTok Downloader", 
            font=("Segoe UI", 18, "bold"), fg=TEXT_WHITE, bg=BG_DARK
        )
        title_lbl.pack(side="left")

        # URL Frame
        url_box = tk.Frame(self.root, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_GRAY)
        url_box.pack(fill="x", padx=24, pady=8)

        url_inner = tk.Frame(url_box, bg=BG_CARD)
        url_inner.pack(fill="x", padx=12, pady=10)

        url_title = tk.Label(url_inner, text="VIDEO URL", font=("Segoe UI", 8, "bold"), fg=ACCENT_CYAN, bg=BG_CARD)
        url_title.pack(anchor="w")

        input_row = tk.Frame(url_inner, bg=BG_CARD)
        input_row.pack(fill="x", pady=(4, 0))

        self.url_entry = tk.Entry(
            input_row, font=("Segoe UI", 10), bg="#2d2d2d", fg=TEXT_WHITE,
            insertbackground=TEXT_WHITE, relief="flat", highlightthickness=1,
            highlightbackground="#3d3d3d"
        )
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        fetch_btn = tk.Button(
            input_row, text="Fetch Preview", command=self._fetch_metadata_thread,
            bg=BORDER_GRAY, fg=TEXT_WHITE, activebackground="#3d3d3d",
            activeforeground=TEXT_WHITE, relief="flat", font=("Segoe UI", 9, "bold"),
            cursor="hand2", padx=12
        )
        fetch_btn.pack(side="right")

        # Preview Card
        self.preview_card = tk.Frame(self.root, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_GRAY)
        self.preview_card.pack(fill="both", expand=True, padx=24, pady=8)

        self.thumb_label = tk.Label(self.preview_card, text="No Video Loaded", fg=TEXT_MUTED, bg="#181818", width=22, height=10)
        self.thumb_label.pack(side="left", padx=16, pady=16)

        info_frame = tk.Frame(self.preview_card, bg=BG_CARD)
        info_frame.pack(side="left", fill="both", expand=True, padx=(0, 16), pady=16)

        self.meta_author = tk.Label(info_frame, text="@author", font=("Segoe UI", 11, "bold"), fg=ACCENT_PINK, bg=BG_CARD, anchor="w")
        self.meta_author.pack(fill="x")

        self.meta_title = tk.Label(
            info_frame, text="Paste or copy a TikTok link to preview details and media stats.",
            font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_CARD, wraplength=320, justify="left", anchor="nw"
        )
        self.meta_title.pack(fill="both", expand=True, pady=(6, 6))

        self.meta_stats = tk.Label(info_frame, text="Likes: -  |  Plays: -", font=("Segoe UI", 8), fg=TEXT_MUTED, bg=BG_CARD, anchor="w")
        self.meta_stats.pack(fill="x")

        # Path Frame
        path_box = tk.Frame(self.root, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_GRAY)
        path_box.pack(fill="x", padx=24, pady=8)

        path_inner = tk.Frame(path_box, bg=BG_CARD)
        path_inner.pack(fill="x", padx=12, pady=10)

        path_title = tk.Label(path_inner, text="SAVE DIRECTORY", font=("Segoe UI", 8, "bold"), fg=ACCENT_CYAN, bg=BG_CARD)
        path_title.pack(anchor="w")

        path_row = tk.Frame(path_inner, bg=BG_CARD)
        path_row.pack(fill="x", pady=(4, 0))

        path_entry = tk.Entry(
            path_row, textvariable=self.download_dir, state="readonly",
            font=("Segoe UI", 9), bg="#2d2d2d", fg=TEXT_MUTED, relief="flat", highlightthickness=1, highlightbackground="#3d3d3d"
        )
        path_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))

        browse_btn = tk.Button(
            path_row, text="Browse", command=self._browse_folder,
            bg=BORDER_GRAY, fg=TEXT_WHITE, activebackground="#3d3d3d",
            activeforeground=TEXT_WHITE, relief="flat", font=("Segoe UI", 9),
            cursor="hand2", padx=12
        )
        browse_btn.pack(side="right")

        # Progress and Status
        prog_frame = tk.Frame(self.root, bg=BG_DARK)
        prog_frame.pack(fill="x", padx=24, pady=4)

        self.progress_bar = ttk.Progressbar(prog_frame, style="Cyan.Horizontal.TProgressbar", mode="determinate")
        self.progress_bar.pack(fill="x", pady=(2, 6))

        self.status_label = tk.Label(prog_frame, textvariable=self.status_text, font=("Segoe UI", 8), fg=TEXT_MUTED, bg=BG_DARK, anchor="w")
        self.status_label.pack(fill="x")

        # Download Button
        self.download_btn = tk.Button(
            self.root, text="DOWNLOAD BEST QUALITY (HD)", command=self._start_download_thread,
            bg=ACCENT_PINK, fg=TEXT_WHITE, activebackground="#e02449",
            activeforeground=TEXT_WHITE, relief="flat", font=("Segoe UI", 11, "bold"),
            cursor="hand2", pady=10
        )
        self.download_btn.pack(fill="x", padx=24, pady=(8, 20))

    def _setup_clipboard_listener(self):
        # Auto-check clipboard whenever the application window gains focus
        self.root.bind("<FocusIn>", lambda e: self._check_clipboard())
        # Periodic background check every 2 seconds
        self._check_clipboard_loop()

    def _check_clipboard_loop(self):
        self._check_clipboard()
        self.root.after(2000, self._check_clipboard_loop)

    def _check_clipboard(self):
        try:
            clip = self.root.clipboard_get().strip()
            if clip and clip != self.last_clipboard:
                if ("tiktok.com" in clip) and clip != self.url_entry.get().strip():
                    self.last_clipboard = clip
                    self.url_entry.delete(0, tk.END)
                    self.url_entry.insert(0, clip)
                    self.status_text.set("Auto-detected link from clipboard!")
                    self._fetch_metadata_thread()
        except tk.TclError:
            pass

    def _browse_folder(self):
        selected = filedialog.askdirectory(initialdir=self.download_dir.get())
        if selected:
            self.download_dir.set(selected)

    def _fetch_metadata_worker(self, url):
        try:
            self.status_text.set("Fetching video metadata...")
            resp = requests.post(
                "https://www.tikwm.com/api/",
                data={"url": url, "hd": 1},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=12
            )
            data = resp.json()

            if data.get("code") != 0 or "data" not in data:
                self.status_text.set("Could not fetch preview.")
                return

            info = data["data"]
            self.current_video_data = info

            # Retrieve & resize cover thumbnail
            cover_url = info.get("cover")
            if cover_url:
                img_resp = requests.get(cover_url, timeout=10)
                img_data = Image.open(io.BytesIO(img_resp.content))
                img_data = img_data.resize((140, 185), Image.Resampling.LANCZOS)
                self.thumb_photo = ImageTk.PhotoImage(img_data)
                self.thumb_label.config(image=self.thumb_photo, text="")

            author_name = info.get("author", {}).get("nickname") or info.get("author", {}).get("unique_id") or "TikTok Creator"
            title_text = info.get("title") or "No title provided"
            digg_count = info.get("digg_count", 0)
            play_count = info.get("play_count", 0)

            self.meta_author.config(text=f"@{author_name}")
            self.meta_title.config(text=title_text[:140] + ("..." if len(title_text) > 140 else ""))
            self.meta_stats.config(text=f"❤️ {digg_count:,} likes   •   👁️ {play_count:,} views")
            self.status_text.set("Ready to download.")

        except Exception:
            self.status_text.set("Failed to load preview.")

    def _fetch_metadata_thread(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        threading.Thread(target=self._fetch_metadata_worker, args=(url,), daemon=True).start()

    def _download_worker(self, url, out_folder):
        try:
            self.status_text.set("Preparing media stream...")
            # If not yet fetched, fetch info first
            if not self.current_video_data:
                resp = requests.post(
                    "https://www.tikwm.com/api/",
                    data={"url": url, "hd": 1},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                    timeout=15
                )
                data = resp.json()
                if data.get("code") != 0 or "data" not in data:
                    raise RuntimeError(data.get("msg", "Failed to retrieve media link."))
                self.current_video_data = data["data"]

            info = self.current_video_data
            video_url = info.get("hdplay") or info.get("play")
            if not video_url:
                raise RuntimeError("No direct playable URL located.")

            video_url = urljoin("https://www.tikwm.com", video_url)
            quality_tag = "HD" if info.get("hdplay") else "SD"
            raw_title = info.get("title") or "tiktok_video"
            clean_title = re.sub(r'[\\/*?:"<>|]', "", raw_title)[:45].strip()
            video_id = info.get("id", "video")
            filepath = os.path.join(out_folder, f"{clean_title} [{video_id}_{quality_tag}].mp4")

            self.status_text.set(f"Downloading stream ({quality_tag})...")

            with requests.get(video_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                total_size = int(r.headers.get("content-length", 0))
                downloaded = 0

                with open(filepath, "wb") as f:
                    for chunk in r.iter_content(chunk_size=131072):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                mb_done = downloaded / (1024 * 1024)
                                mb_tot = total_size / (1024 * 1024)
                                self.progress_bar["value"] = percent
                                self.status_text.set(f"Downloading: {percent:.1f}% ({mb_done:.1f}/{mb_tot:.1f} MB)")

            self.progress_bar["value"] = 100
            self.status_text.set(f"Finished • Saved as {quality_tag}")
            messagebox.showinfo("Download Complete", f"Saved successfully:\n{filepath}")

        except Exception as e:
            self.status_text.set("Download failed.")
            messagebox.showerror("Error", f"Could not download:\n{str(e)}")
        finally:
            self.is_downloading = False
            self.download_btn.config(state="normal")
            self.progress_bar["value"] = 0

    def _start_download_thread(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Missing Link", "Paste a TikTok link first.")
            return

        if self.is_downloading:
            return

        self.is_downloading = True
        self.download_btn.config(state="disabled")
        self.progress_bar["value"] = 0

        threading.Thread(
            target=self._download_worker,
            args=(url, self.download_dir.get()),
            daemon=True
        ).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = TikTokDownloaderApp(root)
    root.mainloop()