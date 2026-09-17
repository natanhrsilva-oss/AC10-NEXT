const AC10_SHEETS = {
  pre: 'AC10 PRE',
  live: 'AC10 LIVE'
};

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || '{}');
    const expected = PropertiesService.getScriptProperties().getProperty('AC10_TOKEN');
    if (!expected || body.token !== expected) return json_({ok:false,error:'unauthorized'});
    const type = String(body.type || '').toLowerCase();
    const name = AC10_SHEETS[type];
    if (!name) return json_({ok:false,error:'invalid type'});
    const rows = Array.isArray(body.rows) ? body.rows : [];
    if (!rows.length) return json_({ok:true,rows:0});
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sh = ss.getSheetByName(name);
    if (!sh) sh = ss.insertSheet(name);
    const headers = Object.keys(rows[0]);
    ensureHeaders_(sh, headers);
    const values = rows.map(r => headers.map(h => r[h] === undefined || r[h] === null ? '' : r[h]));
    sh.getRange(2,1,Math.max(sh.getMaxRows()-1,1),Math.max(sh.getMaxColumns(),headers.length)).clearContent();
    if (sh.getMaxRows() < values.length + 1) sh.insertRowsAfter(sh.getMaxRows(), values.length + 1 - sh.getMaxRows());
    sh.getRange(2,1,values.length,headers.length).setValues(values);
    sh.setFrozenRows(1);
    sh.autoResizeColumns(1, headers.length);
    return json_({ok:true,rows:values.length,sheet:name});
  } catch (err) {
    return json_({ok:false,error:String(err)});
  }
}

function ensureHeaders_(sh, headers) {
  if (sh.getMaxColumns() < headers.length) sh.insertColumnsAfter(sh.getMaxColumns(), headers.length - sh.getMaxColumns());
  sh.getRange(1,1,1,headers.length).setValues([headers]).setFontWeight('bold');
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
