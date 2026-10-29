/**
 * Receives "List your business" submissions and appends each one as a row in a Google Sheet.
 *
 * Setup (once, signed in as the Google account that should own the sheet):
 *  1. Create a Google Sheet. Name the first tab "Listings".
 *  2. In the sheet: Extensions > Apps Script. Paste this whole file over the default code and save.
 *  3. Deploy > New deployment > type "Web app".
 *       Execute as: Me.   Who has access: Anyone.
 *  4. Authorize when asked, then copy the Web app URL (ends in /exec).
 *  5. Paste it into CONFIG.forms.sheet in assets/app.js.
 *
 * After changing this script, use Deploy > Manage deployments > edit > New version; the URL stays the same.
 * The sheet itself stays private; "Anyone" only lets the form post to this script.
 */
var SHEET_NAME = "Listings";
var COLUMNS = ["business", "kind", "contact_email", "contact_phone", "address", "hide_address", "town",
  "where_and_when", "how_to_get_it", "offers", "season", "public_phone", "public_email", "website", "instagram",
  "facebook", "snap", "public_notes", "team_comments"];

function doPost(e) {
  var p = (e && e.parameter) || {};
  if (!p.business || !p.contact_email || !p.contact_phone) return ContentService.createTextOutput("missing fields");

  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["received", "status"].concat(COLUMNS));
      sheet.setFrozenRows(1);
    }
    sheet.appendRow([new Date(), "new"].concat(COLUMNS.map(function (c) { return clean(p[c]); })));
  } finally {
    lock.releaseLock();
  }
  return ContentService.createTextOutput("ok");
}

// A leading = + - @ would make Sheets treat the text as a formula; prefix an apostrophe so it stays text.
function clean(v) {
  v = String(v == null ? "" : v).slice(0, 2000);
  return /^[=+\-@]/.test(v) ? "'" + v : v;
}
