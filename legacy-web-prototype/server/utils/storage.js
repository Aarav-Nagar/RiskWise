import fs from "fs/promises";
import path from "path";

const dataPath = path.join(process.cwd(), "server", "data", "portfolio.json");

async function ensurePortfolioFile() {
  try {
    await fs.access(dataPath);
  } catch {
    await fs.mkdir(path.dirname(dataPath), { recursive: true });
    await fs.writeFile(dataPath, "[]", "utf8");
  }
}

export async function readPortfolioEntries() {
  await ensurePortfolioFile();
  const raw = await fs.readFile(dataPath, "utf8");
  return JSON.parse(raw);
}

export async function appendPortfolioEntry(entry) {
  const entries = await readPortfolioEntries();
  entries.push(entry);
  await fs.writeFile(dataPath, JSON.stringify(entries, null, 2), "utf8");
  return entry;
}
