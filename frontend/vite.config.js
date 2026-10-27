import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  envPrefix: 'VITE_',

  server: {
    host: true, // Tương đương với lệnh --host, cho phép truy cập từ mạng LAN và mạng ngoài
    port: 5173, // Ép Vite luôn chạy đúng cổng này
    strictPort: true, // Nếu cổng 5173 bị kẹt, hệ thống sẽ báo lỗi chứ không tự nhảy sang cổng khác
    allowedHosts: true, // Cho phép các tên miền lạ (như ngrok hay loca.lt) truy cập vào
  }
})
