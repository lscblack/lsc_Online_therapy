import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // usePolling avoids inotify watch exhaustion (ENOSPC) on hosts with a low
  // fs.inotify.max_user_instances limit; safe for dev, ignored in build.
  server: { port: 5173, watch: { usePolling: true, interval: 800 } },
});
