const nextConfig = {
  turbopack: {},
  experimental: {
    cpus: 1,
  },
  webpack: (config: any) => {
    config.watchOptions = {
      poll: 1000,
      aggregateTimeout: 300,
    }
    return config
  },
}

module.exports = nextConfig
