import express from "express";

const app = express();
const port = Number(process.env.PORT || 3000);
const backendUrl = process.env.PUBLIC_BACKEND_URL || "http://localhost:8000";

app.use(express.static("public"));
app.get("/config.js", (_req, res) => {
  res.type("application/javascript").send(`window.ONIONLENS_BACKEND=${JSON.stringify(backendUrl)};`);
});

app.listen(port, "0.0.0.0", () => {
  console.log(`OnionLens frontend listening on ${port}`);
});
