/**
 * Receives "List your business" submissions and keeps them safe.
 *
 * Every submission is stored three ways before the form says "thank you":
 *   1. "Raw" tab: an append-only log of the full submission as JSON. Never edit or sort this tab.
 *   2. "Listings" tab: one tidy row per submission, with a status column for review and approval.
 *   3. A backup email to the account that owns this script.
 * Each submission carries an id from the browser, so a retry never creates a duplicate row.
 *
 * Setup (once, signed in as the Google account that should own the sheet):
 *  1. Create a Google Sheet.
 *  2. In the sheet: Extensions > Apps Script. Paste this whole file over the default code and save.
 *  3. Deploy > New deployment > type "Web app".
 *       Execute as: Me.   Who has access: Anyone.
 *  4. Authorize when asked (it asks for Sheets and email permission), then copy the Web app URL (ends in /exec).
 *  5. Paste it into CONFIG.forms.sheet in assets/app.js.
 *
 * After changing this script, use Deploy > Manage deployments > edit > New version; the URL stays the same.
 * The sheet itself stays private; "Anyone" only lets the form post to this script.
 * Also worth doing: File > Version history keeps changes, and a monthly File > Make a copy keeps an off-site backup.
 */
var SHEET_NAME = "Listings";
var RAW_NAME = "Raw";
var COLUMNS = ["business", "kind", "contact_email", "contact_phone", "address", "hide_address", "town",
  "where_and_when", "how_to_get_it", "offers", "season", "public_phone", "public_email", "website", "instagram",
  "facebook", "snap", "public_notes", "team_comments"];

function doPost(e) {
  var p = (e && e.parameter) || {};
  if (!p.id || !p.business || !p.contact_email || !p.contact_phone) return reply({ ok: false, error: "missing fields" });

  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var raw = ss.getSheetByName(RAW_NAME) || ss.insertSheet(RAW_NAME);
    if (raw.getLastRow() === 0) raw.appendRow(["received", "id", "json"]);

    // Already stored (the browser retried): report success without adding a second row.
    var ids = raw.getLastRow() > 1 ? raw.getRange(2, 2, raw.getLastRow() - 1, 1).getValues() : [];
    for (var i = 0; i < ids.length; i++) if (ids[i][0] === p.id) return reply({ ok: true, id: p.id, duplicate: true });

    var now = new Date();
    raw.appendRow([now, p.id, JSON.stringify(p)]);  // first, so the data is saved even if anything below fails

    var sheet = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["received", "status", "id"].concat(COLUMNS));
      sheet.setFrozenRows(1);
    }
    sheet.appendRow([now, "new", p.id].concat(COLUMNS.map(function (c) { return clean(p[c]); })));

    try {
      MailApp.sendEmail(Session.getEffectiveUser().getEmail(), "New listing: " + p.business,
        COLUMNS.map(function (c) { return c + ": " + (p[c] || ""); }).join("\n") + "\n\nid: " + p.id);
    } catch (mailErr) { /* the row is already saved; a failed backup email must not fail the submission */ }
  } finally {
    lock.releaseLock();
  }
  return reply({ ok: true, id: p.id });
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// A leading = + - @ would make Sheets treat the text as a formula; prefix an apostrophe so it stays text.
function clean(v) {
  v = String(v == null ? "" : v).slice(0, 2000);
  return /^[=+\-@]/.test(v) ? "'" + v : v;
}
