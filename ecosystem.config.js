module.exports = {
  apps: [
    {
      name: "moonyetis-rng",
      script: "./endpoints/rng-server.py",
      interpreter: "python3",
      env: {
        RNG_PORT: 4055,
        RNG_PRICE_SATS: 50000,
      },
      max_restarts: 10,
      restart_delay: 3000,
    },
    {
      name: "moonyetis-balance",
      script: "./endpoints/balance-server.py",
      interpreter: "python3",
      env: {
        BALANCE_PORT: 4056,
        BALANCE_PRICE_SATS: 10000,
      },
      max_restarts: 10,
      restart_delay: 3000,
    },
    {
      name: "moonyetis-timestamp",
      script: "./endpoints/timestamp-server.py",
      interpreter: "python3",
      env: {
        TIMESTAMP_PORT: 4057,
        TIMESTAMP_PRICE_SATS: 200000,
      },
      max_restarts: 10,
      restart_delay: 3000,
    },
  ],
};
