const AC10_SHEETS = {
  pre: 'AC10 PRE',
  live: 'AC10 LIVE',
  pre_history: 'HISTÓRICO PRE',
  live_history: 'HISTÓRICO LIVE'
};

const AC10_COLORS = {
  header: '#17365D',
  headerText: '#FFFFFF',
  blue1: '#D9EAF7',
  blue2: '#BDD7EE',
  recommendation: '#A9D18E',
  green: '#C6EFCE',
  yellow: '#FFEB9C',
  red: '#FFC7CE',
  neutral: '#FFFFFF'
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

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sh = ss.getSheetByName(name);
    if (!sh) sh = ss.insertSheet(name);

    if (!rows.length) {
      if (type === 'pre_history' || type === 'live_history') ensureEmptyHistory_(sh, type);
      return json_({ok:true,rows:0,sheet:name});
    }

    if (type === 'pre_history' || type === 'live_history') {
      upsertHistory_(sh, rows, type);
    } else {
      replaceCurrent_(sh, rows, type);
    }

    return json_({ok:true,rows:rows.length,sheet:name});
  } catch (err) {
    return json_({ok:false,error:String(err)});
  }
}

function ensureEmptyHistory_(sh, type) {
  const common = ['ID','Data','Hora','País','Campeonato','Mandante','Visitante','Mercado','Probabilidade %','Índice','Confiança','Odd','Odd Justa','EV %','Resultado','P/L','Modelo PRE','Modelo LIVE','Criado em','Auditado em'];
  const extra = type === 'pre_history'
    ? ['Precision Score','Qualidade Dados','Margem Mercado','Risco Empate','Prioridade Live','Readiness']
    : ['Minuto','Placar Entrada','Confirmações','Chance Gol 10 min %','Over +1,5 Gols a Mais %','Qualidade Mercado %','Preço'];
  const headers = common.concat(extra);
  ensureHeaders_(sh, headers);
  refreshFilter_(sh, headers.length);
}

function replaceCurrent_(sh, rows, type) {
  const headers = Object.keys(rows[0]);
  ensureHeaders_(sh, headers);
  const values = rows.map(r => headers.map(h => cleanValue_(r[h])));

  const bodyRows = Math.max(sh.getMaxRows() - 1, 1);
  const bodyCols = Math.max(sh.getMaxColumns(), headers.length);
  sh.getRange(2, 1, bodyRows, bodyCols).clearContent().clearFormat();

  if (sh.getMaxRows() < values.length + 1) {
    sh.insertRowsAfter(sh.getMaxRows(), values.length + 1 - sh.getMaxRows());
  }
  sh.getRange(2, 1, values.length, headers.length).setValues(values);
  formatSheet_(sh, headers, values.length, type);
  refreshFilter_(sh, headers.length);
}

function upsertHistory_(sh, rows, type) {
  const headers = Object.keys(rows[0]);
  ensureHeaders_(sh, headers);
  const idCol = headers.indexOf('ID') + 1;
  if (!idCol) throw new Error('History payload requires ID');

  const lastRow = sh.getLastRow();
  const existing = {};
  if (lastRow >= 2) {
    const ids = sh.getRange(2, idCol, lastRow - 1, 1).getValues();
    ids.forEach((v, i) => {
      const id = String(v[0] || '');
      if (id) existing[id] = i + 2;
    });
  }

  const appendValues = [];
  rows.forEach(r => {
    const values = headers.map(h => cleanValue_(r[h]));
    const id = String(r.ID || '');
    const target = existing[id];
    if (target) {
      sh.getRange(target, 1, 1, headers.length).setValues([values]);
    } else {
      appendValues.push(values);
    }
  });

  if (appendValues.length) {
    const start = Math.max(sh.getLastRow() + 1, 2);
    if (sh.getMaxRows() < start + appendValues.length - 1) {
      sh.insertRowsAfter(sh.getMaxRows(), start + appendValues.length - 1 - sh.getMaxRows());
    }
    sh.getRange(start, 1, appendValues.length, headers.length).setValues(appendValues);
  }

  const total = Math.max(sh.getLastRow() - 1, 0);
  formatSheet_(sh, headers, total, type);

  const createdCol = headers.indexOf('Criado em') + 1;
  if (createdCol && total > 1) {
    sh.getRange(2, 1, total, headers.length).sort({column: createdCol, ascending: false});
  }
  refreshFilter_(sh, headers.length);
}

function ensureHeaders_(sh, headers) {
  if (sh.getMaxColumns() < headers.length) {
    sh.insertColumnsAfter(sh.getMaxColumns(), headers.length - sh.getMaxColumns());
  }
  sh.getRange(1, 1, 1, headers.length)
    .setValues([headers])
    .setFontWeight('bold')
    .setBackground(AC10_COLORS.header)
    .setFontColor(AC10_COLORS.headerText)
    .setHorizontalAlignment('center');
  sh.setFrozenRows(1);
}

function refreshFilter_(sh, colCount) {
  const filter = sh.getFilter();
  if (filter) filter.remove();
  sh.getRange(1, 1, Math.max(sh.getLastRow(), 1), colCount).createFilter();
}

function formatSheet_(sh, headers, rowCount, type) {
  if (!rowCount) return;
  const colCount = headers.length;
  const range = sh.getRange(2, 1, rowCount, colCount);
  const values = range.getValues();
  const backgrounds = [];
  const fontWeights = [];

  const statusIdx = headers.indexOf('Status');
  const resultIdx = headers.indexOf('Resultado');
  const metricNames = type === 'live'
    ? ['Índice','Probabilidade %','GPI','IDD Casa','IDD Visitante','Chance Gol 10 min %','Over +1,5 Gols a Mais %','Qualidade Mercado %','Probabilidade Pré %']
    : type === 'pre'
      ? ['Precision Score','Probabilidade Pré %','Índice Pré','Confiança','Qualidade Dados','Perfil Gols','Explosivo','Readiness']
      : ['Probabilidade %','Índice','Confiança','Precision Score','Chance Gol 10 min %','Over +1,5 Gols a Mais %','Qualidade Mercado %'];
  const metricIndexes = metricNames.map(n => headers.indexOf(n)).filter(i => i >= 0);

  for (let r = 0; r < rowCount; r++) {
    const base = r % 2 === 0 ? AC10_COLORS.blue1 : AC10_COLORS.blue2;
    const rowBg = Array(colCount).fill(base);
    const rowWeight = Array(colCount).fill('normal');
    const status = statusIdx >= 0 ? String(values[r][statusIdx] || '') : '';
    const result = resultIdx >= 0 ? String(values[r][resultIdx] || '') : '';

    metricIndexes.forEach(c => {
      const n = Number(values[r][c]);
      if (!isNaN(n) && values[r][c] !== '') {
        if (n > 55) rowBg[c] = AC10_COLORS.green;
        else if (n >= 45) rowBg[c] = AC10_COLORS.yellow;
        else rowBg[c] = AC10_COLORS.red;
        rowWeight[c] = 'bold';
      }
    });

    // An actual offered entry always wins over metric colors.
    if (status === 'RECOMENDAÇÃO') {
      for (let c = 0; c < colCount; c++) {
        rowBg[c] = AC10_COLORS.recommendation;
        rowWeight[c] = 'bold';
      }
    }

    if (result === 'GREEN') {
      for (let c = 0; c < colCount; c++) rowBg[c] = AC10_COLORS.green;
    } else if (result === 'RED') {
      for (let c = 0; c < colCount; c++) rowBg[c] = AC10_COLORS.red;
    }

    backgrounds.push(rowBg);
    fontWeights.push(rowWeight);
  }

  range.setBackgrounds(backgrounds).setFontWeights(fontWeights).setVerticalAlignment('middle');
  sh.autoResizeColumns(1, colCount);

  // Prevent text-heavy columns from becoming absurdly wide.
  ['Campeonato','Mandante','Visitante','Entrada Analisada','Mercado Pré','Persona Casa','Persona Visitante','Preço'].forEach(name => {
    const idx = headers.indexOf(name) + 1;
    if (idx) sh.setColumnWidth(idx, 150);
  });
  ['Atualizado','Criado em','Auditado em'].forEach(name => {
    const idx = headers.indexOf(name) + 1;
    if (idx) sh.setColumnWidth(idx, 170);
  });
}

function cleanValue_(value) {
  return value === undefined || value === null ? '' : value;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
