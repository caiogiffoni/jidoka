import { expect, test } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

import type { Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel(/email/i).fill(`agent-acceptance-${Date.now()}@example.com`);
  await page.getByLabel(/password/i).fill("Password1!");
  await page.getByRole("button", { name: /log in/i }).click();
  await page.waitForURL(`${BASE_URL}/board`);
}

test.describe("agent chat HITL flow", () => {
  test("approving a proposed task creates it on the board", async ({ page }) => {
    await login(page);

    await page.getByRole("button", { name: /agent/i }).click();

    const panel = page.getByRole("complementary", { name: /agent/i });
    await expect(panel).toBeVisible();

    await panel.getByPlaceholder(/ask the agent/i).fill("Add a task called wire HITL flow");
    await panel.getByRole("button", { name: /send/i }).click();

    await expect(panel.getByText("wire HITL flow")).toBeVisible();
    await panel.getByRole("button", { name: /approve/i }).click();

    await expect(
      page.locator('[data-column="todo"]').getByText("wire HITL flow"),
    ).toBeVisible();
  });

  test("rejecting a proposed task does not create it", async ({ page }) => {
    await login(page);

    await page.getByRole("button", { name: /agent/i }).click();
    const panel = page.getByRole("complementary", { name: /agent/i });

    await panel.getByPlaceholder(/ask the agent/i).fill("Add a task called rejected idea");
    await panel.getByRole("button", { name: /send/i }).click();

    await expect(panel.getByText("rejected idea")).toBeVisible();
    await panel.getByRole("button", { name: /reject/i }).click();

    await expect(page.locator("text=rejected idea")).toHaveCount(0);
  });
});
