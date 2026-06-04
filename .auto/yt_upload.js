// YouTube Studio upload via CDP-attached real Chrome (operator-authenticated).
// Drives the Studio upload dialog: file -> title/desc -> not-for-kids -> next x3
// -> unlisted -> done -> harvest the watch URL.
const pw = require("playwright-core");

const FILE = "/Users/kei/projects/sentinel-mesh/film/sentinel-mesh-demo.mp4";
const TITLE = "Sentinel Mesh — Verified-Memory Control Plane for A2A Agent Fleets (Google AI Agents Challenge 2026)";
const DESC = `Every agent memory today is gullible — it stores whatever an agent says. Sentinel Mesh puts an adversarial referee in the A2A message path: a 3-lens Gemini panel judges every claim against memory as ground truth, a deterministic tripwire hard-vetoes money/auth claims with no model in the loop, and what survives is written back, verified. The referee guards memory; memory grounds the referee; the fleet gets more reliable — and cheaper — every run, with zero retraining.

Recorded run (fixture replay) - all counters measured, not asserted.

Dashboard: https://sentinel.k.nexus
Code: https://github.com/gudax/sentinel-mesh
Built with Google ADK - A2A protocol - Gemini on Vertex AI
Nexus AI Labs Inc., Seoul

Track 2 — Google for Startups AI Agents Challenge 2026`;

const shot = async (p, name) => p.screenshot({ path: `/tmp/yt_${name}.png` }).catch(() => {});

(async () => {
  const b = await pw.chromium.connectOverCDP("http://localhost:18222");
  const ctx = b.contexts()[0];
  const p = ctx.pages().find(x => x.url().includes("studio.youtube"));
  if (!p) throw new Error("studio tab not found");

  // dialog opened via Create menu beforehand; if not, open it
  let fileInput = p.locator('input[type="file"]');
  if (!(await fileInput.count())) {
    await p.getByRole("button", { name: /만들기|Create/ }).first().click();
    await p.waitForTimeout(1200);
    await p.getByText(/동영상 업로드|Upload videos/).first().click();
  }
  fileInput = p.locator('input[type="file"]');
  await fileInput.waitFor({ state: "attached", timeout: 30000 });
  await fileInput.setInputFiles(FILE);
  console.log("file set, waiting for details form…");
  await shot(p, "1_file_set");

  // title / description (contenteditable boxes inside the details step)
  const title = p.locator("ytcp-social-suggestions-textbox#title-textarea #textbox, #title-textarea #textbox").first();
  await title.waitFor({ state: "visible", timeout: 60000 });
  await title.click();
  await p.keyboard.press(process.platform === "darwin" ? "Meta+a" : "Control+a");
  await p.keyboard.type(TITLE, { delay: 5 });

  const desc = p.locator("ytcp-social-suggestions-textbox#description-textarea #textbox, #description-textarea #textbox").first();
  await desc.click();
  await p.keyboard.type(DESC, { delay: 2 });
  await shot(p, "2_details");

  // not made for kids
  const nfk = p.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]');
  await nfk.scrollIntoViewIfNeeded();
  await nfk.click();
  await shot(p, "3_nfk");

  // next x3 (details -> elements -> checks -> visibility)
  for (let i = 0; i < 3; i++) {
    await p.locator("#next-button").click();
    await p.waitForTimeout(1500);
  }

  // unlisted
  const unlisted = p.locator('tp-yt-paper-radio-button[name="UNLISTED"]');
  await unlisted.waitFor({ state: "visible", timeout: 30000 });
  await unlisted.click();
  await shot(p, "4_visibility");

  // harvest the short link from the dialog
  const link = p.locator("ytcp-video-info a, a.ytcp-video-info").first();
  let url = "";
  try { url = await link.textContent({ timeout: 10000 }); } catch {}

  // wait for upload to finish enough that Done is clickable, then Done
  await p.locator("#done-button").click();
  console.log("done clicked");
  await p.waitForTimeout(4000);
  await shot(p, "5_done");

  // close confirmation dialog if present
  const closeBtn = p.locator("ytcp-button#close-button, #close-button");
  if (await closeBtn.count()) await closeBtn.first().click().catch(() => {});

  console.log("VIDEO_URL:", (url || "").trim());
  await b.close();
})().catch(async e => { console.error("ERR", e.message); process.exit(1); });
