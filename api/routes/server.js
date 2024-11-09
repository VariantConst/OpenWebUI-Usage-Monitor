const express = require("express");
const bodyParser = require("body-parser");
const { getModelPrices, getOrCreateUser, updateUserBalance } = require("./db");
// 使用 require 语法导入 gpt-tokenizer
const { encode, encodeChat } = require("gpt-tokenizer/cjs/model/gpt-3.5-turbo");

const app = express();
const port = 2811;

const { encode: encode_cl100k_base } = require("gpt-tokenizer");
const { encode: encode_o200k_base } = require("gpt-tokenizer/model/gpt-4o"); // 或 o1

app.use(bodyParser.json());

app.post("/post_user_info", async (req, res) => {
  const { user } = req.body;
  try {
    if (user && user.id) {
      await getOrCreateUser(user);
    }
    res.status(200).json({ status: "success" });
  } catch (error) {
    console.error("Error processing user info:", error);
    res.status(500).json({ error: "Internal server error" });
  }
});

app.post("/post_result", async (req, res) => {
  const { user, model, input_tokens, output_tokens } = req.body;
  try {
    const modelPrices = await getModelPrices(model);
    const totalCost = (
      (input_tokens * modelPrices.input_price +
        output_tokens * modelPrices.output_price) /
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

    const statsText = `\n\n输入 ${input_tokens} tokens，输出 ${output_tokens} tokens，总费用 ¥${totalCost}，账户余额 ¥${newBalance.toFixed(
      4
    )}`;

    // 构建新的响应数据格式
    const responseData = {
      stats_text: statsText,
    };

    res.status(200).json(responseData);
  } catch (error) {
    console.error("Error processing result:", error);
    res.status(500).json({ error: "Internal server error" });
  }
});

app.post("/calculate_tokens", (req, res) => {
  try {
    const { messages, type, model } = req.body;
    let tokenCount;

    // 简化 tokenizer 选择逻辑
    let encodeFunc = /o1|4o/.test(model)
      ? encode_o200k_base
      : encode_cl100k_base;

    console.log(
      `model: ${model}, type: ${type}, encodeFunc: ${
        /o1|4o/.test(model) ? "encode_o200k_base" : "encode_cl100k_base"
      }`
    );
    if (type === "chat") {
      const allContent = messages.map((msg) => msg.content).join("");
      tokenCount = encodeFunc(allContent).length;
    } else {
      // 处理非字符串类型的 messages
      const messageString =
        typeof messages === "string" ? messages : JSON.stringify(messages);
      tokenCount = encodeFunc(messageString).length;
    }
    res.json({ tokens: tokenCount });
  } catch (error) {
    console.error("Error calculating tokens:", error);
    res.status(500).json({ error: "Token calculation failed" });
  }
});

// 启动服务器
app.listen(port, () => {
  console.log(`Server is running on http://localhost:${port}`);
});
