CREATE DATABASE IF NOT EXISTS catclawboard DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE catclawboard;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'user',
  subscription_type VARCHAR(20) DEFAULT NULL,
  subscription_start DATETIME DEFAULT NULL,
  subscription_end DATETIME DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS db_ztdb (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cdate VARCHAR(8) NOT NULL,
  stockid VARCHAR(20) NOT NULL,
  stockname VARCHAR(50),
  zhenfu DECIMAL(10,2),
  declines DECIMAL(10,2),
  INDEX idx_cdate (cdate)
);

CREATE TABLE IF NOT EXISTS db_data_jjztdt (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cdate VARCHAR(8) NOT NULL UNIQUE,
  zts INT DEFAULT 0,
  ztfd DECIMAL(15,2) DEFAULT 0,
  dts INT DEFAULT 0,
  dtfd DECIMAL(15,2) DEFAULT 0,
  INDEX idx_cdate (cdate)
);

CREATE TABLE IF NOT EXISTS db_zrzt_jjvol (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cdate VARCHAR(8) NOT NULL,
  stockid VARCHAR(20) NOT NULL,
  stockname VARCHAR(50),
  zf DECIMAL(10,2),
  zs DECIMAL(10,2),
  volume BIGINT DEFAULT 0,
  jje DECIMAL(15,2) DEFAULT 0,
  rate DECIMAL(10,2) DEFAULT 0,
  status VARCHAR(20),
  INDEX idx_cdate (cdate)
);

CREATE TABLE IF NOT EXISTS db_money_effects (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cdate VARCHAR(8) NOT NULL UNIQUE,
  ztje DECIMAL(15,2) DEFAULT 0,
  maxlb INT DEFAULT 0,
  zts INT DEFAULT 0,
  lbs INT DEFAULT 0,
  yzb INT DEFAULT 0,
  yzbfd DECIMAL(15,2) DEFAULT 0,
  dzfs INT DEFAULT 0,
  INDEX idx_cdate (cdate)
);

CREATE TABLE IF NOT EXISTS db_zt_reson (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cdate VARCHAR(8) NOT NULL,
  stockid VARCHAR(20) NOT NULL,
  stockname VARCHAR(50),
  cje DECIMAL(15,2) DEFAULT 0,
  lbs INT DEFAULT 0,
  reson VARCHAR(200),
  INDEX idx_cdate (cdate),
  UNIQUE KEY uk_cdate_stockid (cdate, stockid)
);

CREATE TABLE IF NOT EXISTS db_large_amount (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cdate VARCHAR(8) NOT NULL,
  stockid VARCHAR(20) NOT NULL,
  amount DECIMAL(20,2) DEFAULT 0,
  INDEX idx_cdate (cdate),
  UNIQUE KEY uk_la_cdate_stockid (cdate, stockid)
);

CREATE TABLE IF NOT EXISTS db_mighty (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cdate VARCHAR(8) NOT NULL,
  stockid VARCHAR(20) NOT NULL,
  stockname VARCHAR(50),
  scores DECIMAL(10,2),
  times VARCHAR(4),
  bzf DECIMAL(10,2),
  cje DECIMAL(15,2),
  rates DECIMAL(10,2),
  ozf DECIMAL(10,2),
  zhenfu DECIMAL(10,2),
  chg_1min DECIMAL(10,2),
  zs_times DECIMAL(3,1),
  tms VARCHAR(5),
  lastzf DECIMAL(10,2),
  INDEX idx_cdate (cdate),
  UNIQUE KEY uk_mighty_cdate_stockid (cdate, stockid)
);

CREATE TABLE IF NOT EXISTS db_lianban (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cdate VARCHAR(8) NOT NULL,
  stockid VARCHAR(20) NOT NULL,
  stockname VARCHAR(50),
  lbs INT DEFAULT 0,
  scores DECIMAL(10,2),
  times VARCHAR(4),
  bzf DECIMAL(10,2),
  cje DECIMAL(15,2),
  rates DECIMAL(10,2),
  ozf DECIMAL(10,2),
  zhenfu DECIMAL(10,2),
  chg_1min DECIMAL(10,2),
  zs_times DECIMAL(3,1),
  tms VARCHAR(5),
  lastzf DECIMAL(10,2),
  UNIQUE KEY uk_lianban_cdate_stockid (cdate, stockid),
  INDEX idx_lianban_cdate (cdate)
);

CREATE TABLE IF NOT EXISTS db_jjmighty (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cdate VARCHAR(8) NOT NULL,
  stockid VARCHAR(20) NOT NULL,
  stockname VARCHAR(50),
  lbs INT DEFAULT 0,
  scores DECIMAL(10,2),
  times VARCHAR(4),
  bzf DECIMAL(10,2),
  cje DECIMAL(15,2),
  rates DECIMAL(10,2),
  ozf DECIMAL(10,2),
  zhenfu DECIMAL(10,2),
  chg_1min DECIMAL(10,2),
  zs_times DECIMAL(3,1),
  tms VARCHAR(5),
  lastzf DECIMAL(10,2),
  UNIQUE KEY uk_jjmighty_cdate_stockid (cdate, stockid),
  INDEX idx_jjmighty_cdate (cdate)
);

CREATE TABLE IF NOT EXISTS db_backtest_runs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  strategy_name VARCHAR(50) NOT NULL,
  strategy_label VARCHAR(100),
  start_date VARCHAR(8) NOT NULL,
  end_date VARCHAR(8) NOT NULL,
  params JSON,
  total_trades INT DEFAULT 0,
  win_trades INT DEFAULT 0,
  win_rate DECIMAL(10,4),
  avg_return DECIMAL(10,4),
  total_return DECIMAL(10,4),
  max_drawdown DECIMAL(10,4),
  sharpe_ratio DECIMAL(10,4),
  profit_factor DECIMAL(10,4),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_bt_strategy (strategy_name)
);

CREATE TABLE IF NOT EXISTS db_backtest_trades (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id INT NOT NULL,
  stockid VARCHAR(20) NOT NULL,
  stockname VARCHAR(50),
  entry_date VARCHAR(8) NOT NULL,
  return_pct DECIMAL(10,4),
  signal_data JSON,
  INDEX idx_trade_run (run_id),
  FOREIGN KEY (run_id) REFERENCES db_backtest_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS db_backtest_equity (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_id INT NOT NULL,
  tdate VARCHAR(8) NOT NULL,
  equity DECIMAL(15,4) NOT NULL,
  drawdown DECIMAL(10,4),
  UNIQUE KEY uk_equity_run_date (run_id, tdate),
  FOREIGN KEY (run_id) REFERENCES db_backtest_runs(id) ON DELETE CASCADE
);
