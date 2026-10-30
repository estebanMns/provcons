import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Permite abrir el servidor de desarrollo desde 127.0.0.1 y desde la IP de
  // la red local además de localhost; sin esto Next 16 bloquea sus recursos de
  // desarrollo y la página no responde.
  allowedDevOrigins: ["127.0.0.1", "192.168.1.108"],
};

export default nextConfig;
