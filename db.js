const sqlite3 = require("sqlite3").verbose();
const path = require("path");

const db = new sqlite3.Database(path.join(__dirname, "models.db"));

// 创建模型价格表
db.serialize(() => {
  db.run(`
    CREATE TABLE IF NOT EXISTS model_prices (
      model_name TEXT PRIMARY KEY,
      input_price REAL NOT NULL,
      output_price REAL NOT NULL
    )
  `);

  // 插入一些默认数据
  const defaultPrices = [
    // OpenAI
    ["gpt-4o-mini", 0.1875, 0.75],
    ["gpt-4o", 0, 0],
    ["chatgpt-4o-latest", 10, 30],
    ["o1-mini", 3, 15],
    ["o1-preview", 15, 75],
    // OpenAI-GF
    ["gpt-4o-mini-gf", 0.1875, 0.75],
    ["gpt-4o-gf", 1.08, 4.32],
    ["chatgpt-4o-latest-gf", 36, 144],
    // Claude
    ["claude-3-5-sonnet-20240620", 9, 45],
    ["claude-3-5-sonnet-20241022", 9, 45],
    ["claude-3-5-haiku-20241022", 3, 15],
    // Claude-GF
    ["claude-3-5-sonnet-20240620-gf", 21.6, 108],
    ["claude-3-5-sonnet-20241022-gf", 21.6, 108],
    ["claude-3-5-haiku-20241022-gf", 7.2, 36],
    // Gemini
    ["gemini-1.5-flash-002", 0, 0],
    ["gemini-1.5-pro-002", 0, 0],
    ["gemini-1.5-flash-002-gf", 0.54, 2.16],
    ["gemini-1.5-pro-002-gf", 9, 36],
    // Others
    ["grok-beta", 0, 0],
    ["meta-llama/llama-3.1-405b-instruct:free", 0, 0],
    ["meta-llama/llama-3.2-90b-vision-instruct:free", 0, 0],
    ["yi-lightning", 0, 0],
    ["qwen-max-latest", 0, 0],
    ["glm-4-plus", 0, 0],
    ["stable-diffusion-35-large", 0, 0],
    ["deepseek-chat", 1, 2],
  ];

  const stmt = db.prepare(
    "INSERT OR REPLACE INTO model_prices VALUES (?, ?, ?)"
  );
  defaultPrices.forEach((price) => stmt.run(price));
  stmt.finalize();
});

// 创建用户表
db.serialize(() => {
  db.run(`
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      name TEXT,
      email TEXT,
      role TEXT,
      balance REAL DEFAULT 10.0
    )
  `);
});

// 获取模型价格的函数
function getModelPrices(modelName) {
  return new Promise((resolve, reject) => {
    db.get(
      "SELECT input_price, output_price FROM model_prices WHERE model_name = ?",
      [modelName],
      (err, row) => {
        if (err) reject(err);
        // 如果没有找到价格，使用默认价格
        resolve(row || { input_price: 60, output_price: 60 });
      }
    );
  });
}

// 获取或创建用户
async function getOrCreateUser(userData) {
  return new Promise((resolve, reject) => {
    if (!userData || !userData.id) {
      console.log("未提供用户数据");
      resolve({ balance: 0 });
      return;
    }

    db.get("SELECT * FROM users WHERE id = ?", [userData.id], (err, row) => {
      if (err) {
        console.error("查询用户时出错:", err);
        reject(err);
        return;
      }

      if (row) {
        resolve(row);
      } else {
        console.log(`创建新用户: ${userData.id}`);
        db.run(
          "INSERT INTO users (id, name, email, role, balance) VALUES (?, ?, ?, ?, 10.0)",
          [
            userData.id,
            userData.name || "",
            userData.email || "",
            userData.role || "user",
          ],
          function (err) {
            if (err) {
              console.error("创建用户时出错:", err);
              reject(err);
              return;
            }
            console.log(`新用户已创建: ${userData.id}, 初始余额: 10.0`);
            resolve({
              id: userData.id,
              name: userData.name || "",
              email: userData.email || "",
              role: userData.role || "user",
              balance: 10.0,
            });
          }
        );
      }
    });
  });
}

// 更新用户余额
async function updateUserBalance(userId, cost) {
  if (!userId) return 0;

  return new Promise((resolve, reject) => {
    db.get("SELECT balance FROM users WHERE id = ?", [userId], (err, row) => {
      if (err) {
        reject(err);
        return;
      }

      if (!row) {
        db.run(
          "INSERT INTO users (id, balance) VALUES (?, 10.0)",
          [userId],
          (err) => {
            if (err) {
              reject(err);
              return;
            }
            resolve(10.0 - cost);
          }
        );
      } else {
        const newBalance = Math.max(0, row.balance - cost);
        db.run(
          "UPDATE users SET balance = ? WHERE id = ?",
          [newBalance, userId],
          (err) => {
            if (err) {
              reject(err);
              return;
            }
            resolve(newBalance);
          }
        );
      }
    });
  });
}

module.exports = { getModelPrices, getOrCreateUser, updateUserBalance };
