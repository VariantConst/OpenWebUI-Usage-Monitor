const express = require("express");
const bodyParser = require("body-parser");
const { getModelPrices, getOrCreateUser, updateUserBalance } = require("./db");
const app = express();
const port = 2811;

// 使用内存数据库来模拟数据存储
const sessions = new Map();

app.use(bodyParser.json());

app.post("/post_user_info", async (req, res) => {
  const { body, user } = req.body;

  // 从 body 中获取 chat_id
  const chat_id = body?.metadata?.chat_id;

  if (!chat_id) {
    return res
      .status(400)
      .json({ error: "chat_id is required in body.metadata" });
  }

  try {
    // 如果有用户信息，立即创建或获取用户
    console.log("user", user);
    if (user && user.id) {
      await getOrCreateUser(user);
      console.log(`User created/verified: ${user.id}`);
    }

    // 存储会话数据
    const sessionData = {
      body,
      user,
      timestamp: Date.now(),
      original_request: req.body,
    };

    sessions.set(chat_id, sessionData);

    console.log(`Stored data for chat_id: ${chat_id}`);
    res.status(200).json({ status: "success", chat_id });
  } catch (error) {
    console.error("Error processing user info:", error);
    res.status(500).json({ error: "Internal server error" });
  }
});

const calculateTokens = (chars) => {
  return Math.ceil(chars / 2.718 + 2);
};

app.post("/post_result", async (req, res) => {
  const { session_id, body, user, llm_response } = req.body;

  if (!session_id) {
    return res.status(400).json({ error: "session_id is required" });
  }

  try {
    // 获取会话数据
    const sessionData = sessions.get(session_id);
    if (!sessionData) {
      return res.status(404).json({ error: "session not found" });
    }

    // 计算 tokens
    const inputTokens = calculateTokens(
      sessionData.original_request.body.messages.reduce(
        (sum, msg) => sum + msg.content.length,
        0
      )
    );
    const outputTokens = calculateTokens(llm_response.length);

    // 获取模型价格
    const modelPrices = await getModelPrices(body.model);

    // 计算总价格（单位：美元）
    const totalCost = (
      (inputTokens * modelPrices.input_price +
        outputTokens * modelPrices.output_price) /
      1000000
    ).toFixed(4);

    // 更新用户余额并获取新余额
    const userId = user?.id;
    let newBalance = 0;

    try {
      newBalance = await updateUserBalance(userId, parseFloat(totalCost));
    } catch (error) {
      console.error("Error updating balance:", error);
      newBalance = 0; // 如果出错，使用默认值
    }

    const statsText = `\n\n本次对话统计：输入 ${inputTokens} tokens，输出 ${outputTokens} tokens，总费用 ¥${totalCost}，账户余额 ¥${newBalance.toFixed(
      4
    )}`;

    // 构建新的响应数据格式
    const responseData = {
      session_id: session_id,
      model: body.model,
      messages: sessionData.original_request.body.messages,
      llm_response: llm_response,
      stats_text: statsText,
      remaining_balance: newBalance,
    };

    // 更新会话的最后时间戳
    sessions.set(session_id, { ...sessionData, timestamp: Date.now() });

    res.status(200).json(responseData);
  } catch (error) {
    console.error("Error processing result:", error);
    res.status(500).json({ error: "Internal server error" });
  }
});

// 启动服务器
app.listen(port, () => {
  console.log(`Server is running on http://localhost:${port}`);
});
