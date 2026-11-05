// Drives the review app in a real browser. Started by test_review_ui.py, which runs
// the server against a fake hub with real audio.
import assert from 'node:assert/strict'
import { chromium } from 'playwright-core'

const [, , base, shots] = process.argv
const CHROME = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const browser = await chromium.launch({ executablePath: CHROME, headless: true })
const page = await browser.newPage({ viewport: { width: 1200, height: 1000 } })
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
const step = (s) => console.log('  ok', s)
const button = (name) => page.getByRole('button', { name, exact: true })
const body = () => page.textContent('body')

try {
  // sign in
  await page.goto(base)
  await page.getByLabel('Access token').fill('wrong')
  await button('Connect').click()
  await page.getByText("Hugging Face didn't accept that token.").waitFor()
  await page.getByLabel('Access token').fill('good')
  await button('Connect').click()
  await page.getByText('Signed in as from-token').waitFor()
  step('sign in, including a wrong token')

  // batches: taken ones can't be claimed
  assert.match(await body(), /Claimed by someone-else/)
  assert.equal(await button('Claim').count(), 1)
  await button('Claim').click()
  await page.waitForURL('**/batch/c1-review-0001')
  await page.getByText('0 of 2 clips done').waitFor()
  await button('Start reviewing').click()
  await page.waitForURL('**/clip/a')
  step('claim opens the batch')

  // a segment plays only its own part of the recording
  await page.getByRole('button', { name: 'Play segment 2' }).click()
  await page.waitForFunction(() => { const a = document.querySelector('audio'); return a.currentTime > 2.1 && !a.paused })
  await page.waitForFunction(() => document.querySelector('audio').paused, null, { timeout: 8000 })
  const stopped = await page.evaluate(() => document.querySelector('audio').currentTime)
  assert.ok(stopped >= 3.9 && stopped < 4.6, `stopped at ${stopped}`)
  step(`segment 2 (2-4 s) played and stopped at ${stopped.toFixed(2)} s`)

  // can't finish until every segment is covered, and untouched boxes stay null
  assert.ok(await button('Mark reviewed').isDisabled())
  await page.getByLabel('Translation 1').fill('Fever for two days.')
  await page.getByLabel('Translation 1').blur()
  await page.getByRole('button', { name: 'Accept as is' }).nth(1).click()   // transcript 2: translation 1's button is gone
  await page.getByText('All segments reviewed.').waitFor()
  await page.reload()
  await page.getByLabel('Translation 1').waitFor()
  assert.equal(await page.getByLabel('Translation 1').inputValue(), 'Fever for two days.')
  const saved = await page.evaluate(async () => (await (await fetch('/api/batches/c1-review-0001')).json()).clips[0].segments)
  assert.equal(saved[0].final_translation, 'Fever for two days.')
  assert.equal(saved[0].final_transcript, null)
  assert.equal(saved[1].final_transcript, 'generated transcript 1')
  assert.equal(saved[1].final_translation, null)
  step('edits save to disk, survive a reload, and untouched drafts stay null')

  await page.screenshot({ path: `${shots}/clip.png`, fullPage: true })
  await page.setViewportSize({ width: 390, height: 800 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth), 0)
  await page.setViewportSize({ width: 1200, height: 1000 })
  step('no sideways scrolling at phone width')

  // languages: a bad code is refused, English hides translation, and it persists
  await page.getByLabel('Spoken languages').fill('malayalam')
  await page.getByLabel('Spoken languages').blur()
  await page.getByText('Use language codes such as ml or en.').waitFor()
  await page.getByLabel('Spoken languages').fill('en')
  await page.getByLabel('Spoken languages').blur()
  await page.getByText("English-only audio doesn't need a translation.").waitFor()
  assert.equal(await page.getByLabel('Translation 1').count(), 0)
  await page.getByLabel('Spoken languages').fill('ml, en')
  await page.getByLabel('Spoken languages').blur()
  await page.getByLabel('Translation 1').waitFor()
  step('language box validates and controls the translation boxes')

  await page.getByLabel('Category').selectOption('medical-scribe')
  await button('Mark reviewed').click()
  await page.waitForURL('**/clip/b')
  step('Mark reviewed moves straight to the next clip')

  // no usable speech covers a segment; flagging needs no text
  await page.getByLabel('No usable speech').first().check()
  await button('Flag clip').click()
  await page.waitForURL('**/batch/c1-review-0001')
  await page.getByText('2 of 2 clips done').waitFor()
  await button('Submit batch').click()
  await page.getByText('Submitted 2 clips').waitFor()
  step('flag, then submit the batch')

  await page.goto(base)
  await page.getByText('Submitted, waiting for the maintainer').waitFor()
  step('batch shows as submitted')
  assert.deepEqual(errors, [])
} catch (e) {
  await page.screenshot({ path: `${shots}/failure.png`, fullPage: true }).catch(() => {})
  console.error('FAIL', e.message)
  process.exitCode = 1
} finally {
  await browser.close()
}
