import { encode, decode, isWithinTokenLimit, encodeChat } from "gpt-tokenizer";

// 测试基本的编码和解码功能
console.log("=== 测试基本编码和解码 ===");
const text = "Hello, world!";
const tokens = encode(text);
console.log("原始文本:", text);
console.log("编码后的令牌:", tokens);
const decodedText = decode(tokens);
console.log("解码后的文本:", decodedText);
console.log("编码解码是否一致:", text === decodedText);
console.log("\n");

// 测试令牌限制检查功能
console.log("=== 测试令牌限制 ===");
const shortText = "Short text for testing.";
const tokenLimit = 10;
const withinLimit = isWithinTokenLimit(shortText, tokenLimit);
console.log("文本:", shortText);
console.log("令牌限制:", tokenLimit);
console.log("是否在限制内:", withinLimit !== false);
console.log("实际令牌数:", withinLimit === false ? "超出限制" : withinLimit);
console.log("\n");

// 测试聊天消息编码
console.log("=== 测试聊天消息编码 ===");
const chat = [
  { role: "system", content: "You are a helpful assistant." },
  { role: "user", content: "Hello!" },
  { role: "assistant", content: "Hi! How can I help you today?" },
];
const chatTokens = encodeChat(chat, "gpt-3.5-turbo");
console.log("聊天消息:", JSON.stringify(chat, null, 2));
console.log("编码后的聊天令牌:", chatTokens);
console.log("聊天消息令牌数量:", chatTokens.length);
