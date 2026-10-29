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
var COLUMNS = ["business", "kind", "how_to_get_it", "where_and_when", "offers", "address", "hide_address",
  "lat", "lon", "town", "season", "phone", "email", "website", "snap", "notes"];

function doPost(e) {
  var p = (e && e.parameter) || {};
  if (!p.business || !p.phone) return ContentService.createTextOutput("missing fields");

  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["received", "status"].concat(COLUMNS));
      sheet.setFrozenRows(1);
    }
    var row = ["", "new"].concat(COLUMNS.map(function (c) { return clean(p[c]); }));
    row[0] = new Date();
    sheet.appendRow(row);
  } finally {
    lock.releaseLock();
  }
  return ContentService.createTextOutput("ok");
}

// A leading = + - @ would make Sheets treat the text as a formula; prefix an apostrophe so it stays text.
function clean(v) {
  v = String(v == null ? "" : v).slice(0, 2000);
  if (/^-?\d+(\.\d+)?$/.test(v)) return v;  // plain numbers, e.g. a negative longitude
  return /^[=+\-@]/.test(v) ? "'" + v : v;
}
