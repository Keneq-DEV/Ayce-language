/**
 * ayce — extensión para VS Code (v0.6.3)
 *
 * Comandos:
 *   ayce.runFile             — ejecuta el .ayce en el panel de salida
 *   ayce.runFileInTerminal   — ejecuta el .ayce en la terminal integrada
 *   ayce.setupCodeRunner     — configura Code Runner
 *   ayce.applyColors         — aplica la paleta "Ayce Dusk" (se adapta al tema claro/oscuro)
 *   ayce.removeColors        — quita TODOS los colores de ayce de tus settings
 *
 * v0.6.3 (diseño del cliente): State/box y el guard principal <GUARD>-<MAIN>.
 * Criterio del cliente: cada token nuevo lleva COLOR PROPIO (no reutilizado).
 * La paleta suma 12 categorías, elegidas por ΔE (Lab) contra todos los colores
 * existentes y contraste WCAG >= 4.5:1:
 *   state (State), box (deja de compartir el color de self), armtype (el
 *   'type' de los brazos), fallback (el 'null' de reserva), guard (GUARD),
 *   main (MAIN), gdelim (la puntuación de <GUARD>-<MAIN>), sdash (el '-' que
 *   conecta el sujeto), sangle (los < > del bloque), y hexpre/octpre/binpre —
 *   los prefijos 0x, 0o y 0b ahora CADA UNO con su color, separados de los
 *   dígitos (que conservan radix).
 */

const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const cp = require('child_process');

/* ------------------------------------------------------------------ */
/*  Paleta "Ayce Dusk"                                                 */
/*  Tonos apagados de luminosidad media: no deslumbran en oscuro y     */
/*  no se lavan en claro. Contraste >= 4.5:1 en fondos típicos.        */
/* ------------------------------------------------------------------ */

const PALETTES = {
  dark: {
    comment: '#8A97AE', string: '#E8A27C', escape: '#F2C2A8', int: '#E6B665',
    float: '#6FD0B0', bool: '#62C6E4', bytes: '#5CCFC0', none: '#E88FBA',
    modifier: '#D9A85F', control: '#8EA6F2', decl: '#C29DEC', error: '#EE7F8E',
    io: '#D58BE0', builtin: '#6FD0B0', fn: '#D2DA8E', operator: '#D9A0C8',
    bracket: '#C4B48A', punct: '#8C98AD', constant: '#E6B665', variable: '#8FD68A',
    radix: '#FF6B47', collection: '#2ED573',
    state: '#DF49DF', box: '#B7DF49', armtype: '#8774E7', fallback: '#DF49AD',
    guard: '#6CDF49', main: '#DFCB49', gdelim: '#D46D54', sdash: '#49DFA3',
    sangle: '#CE8F8D', hexpre: '#E35F98', octpre: '#97E774', binpre: '#9FD6D6',
    module: '#49A3DF',
  },
  light: {
    comment: '#5E6F85', string: '#A8531F', escape: '#8A4318', int: '#8F5E00',
    float: '#0B7D5F', bool: '#0A7396', bytes: '#0F7A69', none: '#B63A78',
    modifier: '#85600E', control: '#4357C9', decl: '#7F45BD', error: '#BE3550',
    io: '#9A3DB0', builtin: '#0B7D5F', fn: '#66730C', operator: '#9A3F85',
    bracket: '#7D683A', punct: '#5F6B80', constant: '#8F5E00', variable: '#2F7D32',
    radix: '#C13E1C', collection: '#11804C',
    state: '#2525D0', box: '#3A4A88', armtype: '#D025A2', fallback: '#883A4C',
    guard: '#A933DB', main: '#2575D0', gdelim: '#1D26A5', sdash: '#663A88',
    sangle: '#AB5349', hexpre: '#DB333E', octpre: '#6921BA', binpre: '#2C72AF',
    module: '#C431C4',
  },
};

const RULE_PREFIX = 'ayce-palette:';

function buildRules(p) {
  const r = (id, scope, color, fontStyle) => ({
    name: RULE_PREFIX + id,
    scope,
    settings: fontStyle ? { foreground: color, fontStyle } : { foreground: color },
  });
  return [
    r('comment', ['comment.line.double-hash.ayce', 'comment.block.ayce'], p.comment, 'italic'),
    r('string', ['string.quoted.double.ayce', 'storage.type.string.ayce'], p.string),
    r('escape', ['constant.character.escape.ayce'], p.escape),
    r('int', ['constant.numeric.integer.ayce', 'storage.type.int.ayce'], p.int),
    r('float', ['constant.numeric.float.ayce', 'storage.type.float.ayce'], p.float),
    r('bool', ['constant.language.boolean.ayce', 'storage.type.bool.ayce'], p.bool),
    r('bytes', ['storage.type.bytes.ayce', 'string.quoted.double.bytes.ayce'], p.bytes),
    r('none', ['constant.language.null.ayce', 'storage.type.none.ayce'], p.none),
    r('modifier', ['storage.modifier.ayce'], p.modifier, 'italic'),
    r('control', [
      'keyword.control.conditional.ayce',
      'keyword.control.loop.ayce',
      'keyword.control.flow.ayce',
      'keyword.control.match.ayce',
    ], p.control),
    r('decl', [
      'keyword.other.declaration.ayce',
      'keyword.other.function.ayce',
      'keyword.other.type-decl.ayce',
      'keyword.other.new.ayce',
    ], p.decl),
    r('error', ['keyword.control.error.ayce'], p.error),
    r('self', ['variable.language.self.ayce'], p.error, 'italic'),
    // v0.6.3: box deja de compartir el color de self — cada cosa su color.
    r('box', ['variable.language.box.ayce'], p.box, 'italic'),
    // v0.6.3: State y guard principal del cliente, cada token con el suyo.
    r('state', ['keyword.control.state.ayce'], p.state, 'bold'),
    r('armtype', ['keyword.control.type.ayce'], p.armtype),
    r('fallback', ['keyword.control.fallback.ayce'], p.fallback),
    r('guard', ['keyword.control.guard.ayce'], p.guard, 'bold'),
    r('main', ['keyword.control.main.ayce'], p.main),
    r('gdelim', ['punctuation.definition.guard.ayce'], p.gdelim, 'bold'),
    r('sdash', ['keyword.operator.state-connect.ayce'], p.sdash, 'bold'),
    r('sangle', ['punctuation.definition.state-angle.ayce'], p.sangle, 'bold'),
    // v0.6.3: prefijos 0x/0o/0b — cada uno con su color, separados de los dígitos.
    r('hexpre', ['constant.numeric.radix.hex.ayce'], p.hexpre, 'bold'),
    r('octpre', ['constant.numeric.radix.oct.ayce'], p.octpre, 'bold'),
    r('binpre', ['constant.numeric.radix.bin.ayce'], p.binpre, 'bold'),
    r('io', ['keyword.other.io.ayce'], p.io),
    // v0.6.3: require/from/as dejan de quedar sin color — cada cosa la suya.
    r('module', ['keyword.control.module.ayce'], p.module),
    r('builtin', ['support.function.builtin.ayce'], p.builtin),
    r('collection', [
      'storage.type.list.ayce',
      'storage.type.dict.ayce',
      'storage.type.tuple.ayce',
      'storage.type.set.ayce',
    ], p.collection),
    r('radix', ['constant.numeric.radix.ayce'], p.radix),
    r('function', ['entity.name.function.ayce'], p.fn),
    r('operator', [
      'keyword.operator.arithmetic.ayce',
      'keyword.operator.comparison.ayce',
      'keyword.operator.logical.ayce',
      'keyword.operator.assignment.ayce',
      'keyword.operator.ternary.ayce',
      'keyword.operator.arrow.ayce',
      'keyword.operator.pipe.ayce',
      'keyword.operator.varargs.ayce',
      'keyword.operator.bitwise.ayce',
    ], p.operator),
    r('bracket', [
      'punctuation.definition.brackets.ayce',
      'punctuation.definition.braces.ayce',
      'punctuation.definition.parens.ayce',
      'punctuation.definition.angle.ayce',
    ], p.bracket),
    r('punct', [
      'punctuation.separator.colon.ayce',
      'punctuation.separator.semicolon.ayce',
      'punctuation.separator.comma.ayce',
      'punctuation.accessor.dot.ayce',
    ], p.punct),
    r('constant', ['variable.other.constant.ayce'], p.constant, 'bold'),
    r('variable', ['variable.other.ayce'], p.variable),
  ];
}

function pickPalette() {
  const cfg = vscode.workspace.getConfiguration('ayce');
  const mode = cfg.get('colors.mode') || 'auto';
  const K = vscode.ColorThemeKind;
  const kind = vscode.window.activeColorTheme.kind;
  const isLight = mode === 'light' || (mode === 'auto' && (kind === K.Light || kind === K.HighContrastLight));
  const base = isLight ? PALETTES.light : PALETTES.dark;
  // Colores propios del usuario: "ayce.colors.overrides": { "variable": "#8FD68A" }
  const overrides = cfg.get('colors.overrides') || {};
  const out = Object.assign({}, base);
  for (const key of Object.keys(overrides)) {
    if (key in base && /^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/.test(String(overrides[key]))) {
      out[key] = overrides[key];
    }
  }
  return out;
}

/** ¿La regla pertenece a ayce? (cualquier scope que termine en .ayce) */
function isAyceRule(rule) {
  if (!rule || rule.scope === undefined) return false;
  const scopes = Array.isArray(rule.scope) ? rule.scope : String(rule.scope).split(',');
  return scopes.some(s => /\.ayce\s*$/.test(String(s).trim()));
}

function isOurRule(rule) {
  return !!rule && typeof rule.name === 'string' && rule.name.startsWith(RULE_PREFIX);
}

/**
 * Devuelve una copia del objeto tokenColorCustomizations sin las reglas de ayce
 * (también dentro de bloques por tema como "[Monokai]").
 * all=true  -> quita toda regla .ayce (incluye las viejas sin etiqueta)
 * all=false -> sólo quita las que puso esta extensión
 */
function stripRules(obj, all) {
  const out = JSON.parse(JSON.stringify(obj || {}));
  const shouldDrop = all ? isAyceRule : isOurRule;
  const clean = (node) => {
    if (Array.isArray(node.textMateRules)) {
      node.textMateRules = node.textMateRules.filter(r => !shouldDrop(r));
      if (node.textMateRules.length === 0) delete node.textMateRules;
    }
  };
  clean(out);
  for (const key of Object.keys(out)) {
    if (key.startsWith('[') && out[key] && typeof out[key] === 'object') {
      clean(out[key]);
      if (Object.keys(out[key]).length === 0) delete out[key];
    }
  }
  return out;
}

const SETTING = 'editor.tokenColorCustomizations';

async function writeTargets(transform) {
  const cfg = vscode.workspace.getConfiguration();
  const info = cfg.inspect(SETTING) || {};
  const targets = [[vscode.ConfigurationTarget.Global, info.globalValue, true]];
  if (vscode.workspace.workspaceFolders) {
    targets.push([vscode.ConfigurationTarget.Workspace, info.workspaceValue, false]);
  }
  for (const [target, current, isGlobal] of targets) {
    if (!current && !isGlobal) continue;
    const next = transform(current || {}, isGlobal);
    if (next === null) continue;
    if (JSON.stringify(next) === JSON.stringify(current || {})) continue;
    await cfg.update(SETTING, Object.keys(next).length ? next : undefined, target);
  }
}

let applying = Promise.resolve();

function applyColors(context, opts = {}) {
  // Se serializa para que dos eventos seguidos (cambio de tema + settings) no se pisen.
  applying = applying.then(() => doApplyColors(context, opts)).catch((e) => {
    if (!opts.silent) vscode.window.showErrorMessage(`No se pudieron aplicar los colores: ${e.message}`);
  });
  return applying;
}

async function doApplyColors(context, opts) {
  const mode = vscode.workspace.getConfiguration('ayce').get('colors.mode') || 'auto';
  const MIGRATED = 'ayce.legacyColorsCleaned.v1';
  // Primera vez con esta versión (o aplicación manual): limpiar cualquier color viejo de ayce.
  const wipeLegacy = !!opts.force || !context.globalState.get(MIGRATED);

  if (mode === 'off') {
    await writeTargets((cur) => stripRules(cur, wipeLegacy));
    return;
  }

  const rules = buildRules(pickPalette());
  await writeTargets((cur, isGlobal) => {
    const next = stripRules(cur, wipeLegacy);
    if (!isGlobal) return next; // en el workspace sólo limpiamos
    next.textMateRules = [...(next.textMateRules || []), ...rules];
    return next;
  });
  await context.globalState.update(MIGRATED, true);

  if (opts.force) {
    vscode.window.showInformationMessage('Paleta de ayce aplicada. Se adapta sola si cambiás de tema claro/oscuro.');
  }
}

async function removeColors(context) {
  try {
    await writeTargets((cur) => stripRules(cur, true));
    await vscode.workspace.getConfiguration('ayce').update('colors.mode', 'off', vscode.ConfigurationTarget.Global);
    await context.globalState.update('ayce.legacyColorsCleaned.v1', true);
    vscode.window.showInformationMessage(
      'Se quitaron todos los colores de ayce. Para volver a ponerlos: "ayce: Aplicar colores de sintaxis".'
    );
  } catch (e) {
    vscode.window.showErrorMessage(`No se pudieron quitar los colores: ${e.message}`);
  }
}

/* ------------------------------------------------------------------ */
/*  Ejecución                                                          */
/* ------------------------------------------------------------------ */

function isWindows() {
  return process.platform === 'win32';
}

function defaultPython() {
  return isWindows() ? 'python' : 'python3';
}

/** 'powershell' | 'cmd' | 'posix' según la shell de la terminal integrada. */
function shellKind() {
  if (!isWindows()) return 'posix';
  const s = (vscode.env.shell || '').toLowerCase();
  if (s.includes('cmd.exe') || /[\\/]cmd$/.test(s)) return 'cmd';
  if (s.includes('bash') || s.endsWith('/sh') || s.endsWith('\\sh.exe') || s.includes('zsh')) return 'posix';
  return 'powershell';
}

function quoteArg(s, kind) {
  if (kind === 'powershell') return "'" + s.replace(/'/g, "''") + "'";
  if (kind === 'cmd') return '"' + s.replace(/"/g, '""') + '"';
  return '"' + s.replace(/(["\\$`])/g, '\\$1') + '"';
}

function resolveInterpreterTokens() {
  const config = vscode.workspace.getConfiguration('ayce');
  const pythonPath = config.get('pythonPath') || defaultPython();
  const interpreterPath = config.get('interpreterPath');

  if (interpreterPath && interpreterPath.trim().length > 0) {
    if (interpreterPath.endsWith('.py')) {
      return [pythonPath, interpreterPath];
    }
    return [interpreterPath];
  }

  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (workspaceFolders) {
    for (const folder of workspaceFolders) {
      const candidate = path.join(folder.uri.fsPath, 'tools', 'ayce_cli.py');
      if (fs.existsSync(candidate)) {
        return [pythonPath, candidate];
      }
      const parentCandidate = path.join(folder.uri.fsPath, '..', 'tools', 'ayce_cli.py');
      if (fs.existsSync(parentCandidate)) {
        return [pythonPath, parentCandidate];
      }
    }
  }

  return [pythonPath, '-m', 'ayce'];
}

function buildCommand(filePath, kind) {
  const tokens = resolveInterpreterTokens();
  const parts = tokens.map(t => {
    if (t === '-m' || t === 'ayce') return t;
    return /[\s"'`$&()]/.test(t) ? quoteArg(t, kind) : t;
  });
  parts.push(quoteArg(filePath, kind));
  const cmd = parts.join(' ');
  return kind === 'powershell' ? '& ' + cmd : cmd;
}

/** Comando para la terminal integrada (respeta PowerShell / cmd / bash). */
function buildTerminalCommand(filePath) {
  return buildCommand(filePath, shellKind());
}

/** Comando para cp.exec (panel de salida). */
function buildExecCommand(filePath) {
  return buildCommand(filePath, isWindows() ? 'powershell' : 'posix');
}

function getActiveAyceEditor() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage('No hay un editor activo.');
    return null;
  }
  if (editor.document.languageId !== 'ayce' && !editor.document.fileName.endsWith('.ayce')) {
    vscode.window.showWarningMessage('El archivo activo no es .ayce.');
    return null;
  }
  return editor;
}

let outputChannel;
function getOutput() {
  if (!outputChannel) outputChannel = vscode.window.createOutputChannel('ayce');
  return outputChannel;
}

async function runFile() {
  const editor = getActiveAyceEditor();
  if (!editor) return;

  const config = vscode.workspace.getConfiguration('ayce');
  if (config.get('saveBeforeRun')) {
    await editor.document.save();
  }

  const filePath = editor.document.uri.fsPath;
  const fullCmd = buildExecCommand(filePath);

  const output = getOutput();
  if (config.get('clearOutputBeforeRun')) {
    output.clear();
  }
  output.show(true);
  output.appendLine(`> ${fullCmd}`);
  output.appendLine('');

  const shellOpts = {
    cwd: path.dirname(filePath),
    shell: isWindows() ? 'powershell.exe' : undefined,
  };
  cp.exec(fullCmd, shellOpts, (err, stdout, stderr) => {
    if (stdout) output.append(stdout);
    if (stderr) output.append(stderr);
    output.appendLine('');
    output.appendLine(err ? `(proceso terminó con código ${err.code || 1})` : '(proceso terminó OK)');
  });
}

async function runFileInTerminal() {
  const editor = getActiveAyceEditor();
  if (!editor) return;

  const config = vscode.workspace.getConfiguration('ayce');
  if (config.get('saveBeforeRun')) {
    await editor.document.save();
  }

  const filePath = editor.document.uri.fsPath;
  const fullCmd = buildTerminalCommand(filePath);

  const terminal = vscode.window.createTerminal({
    name: `ayce: ${path.basename(filePath)}`,
    cwd: path.dirname(filePath),
  });
  terminal.show();
  terminal.sendText(fullCmd, true);
}

async function setupCodeRunner() {
  const codeRunnerExt = vscode.extensions.getExtension('formulahendry.code-runner');
  if (!codeRunnerExt) {
    const action = await vscode.window.showWarningMessage(
      'Code Runner no está instalado. ¿Abrir el marketplace?',
      'Abrir marketplace',
      'Cancelar'
    );
    if (action === 'Abrir marketplace') {
      vscode.commands.executeCommand('workbench.extensions.search', 'code-runner');
    }
    return;
  }

  const tokens = resolveInterpreterTokens().map(t => (/\s/.test(t) ? `"${t}"` : t));
  const executorCmd = [...tokens, '$filePath'].join(' ');

  const config = vscode.workspace.getConfiguration();
  const current = config.get('code-runner.executorMap');
  const executorMap = Object.assign({}, current && typeof current === 'object' ? current : {});
  executorMap['ayce'] = executorCmd;

  try {
    await config.update('code-runner.executorMap', executorMap, vscode.ConfigurationTarget.Global);
    vscode.window.showInformationMessage(`Code Runner configurado: ${executorCmd}`);
  } catch (e) {
    vscode.window.showErrorMessage(`No se pudo actualizar: ${e.message}`);
  }
}

/* ------------------------------------------------------------------ */

function activate(context) {
  const reg = (id, fn) => context.subscriptions.push(vscode.commands.registerCommand(id, fn));
  reg('ayce.runFile', () => runFile());
  reg('ayce.runFileInTerminal', () => runFileInTerminal());
  reg('ayce.setupCodeRunner', () => setupCodeRunner());
  reg('ayce.applyColors', async () => {
    // Aplicar a mano reactiva la paleta aunque estuviera en "off".
    const cfg = vscode.workspace.getConfiguration('ayce');
    if (cfg.get('colors.mode') === 'off') {
      await cfg.update('colors.mode', 'auto', vscode.ConfigurationTarget.Global);
    }
    await applyColors(context, { force: true });
  });
  reg('ayce.removeColors', () => removeColors(context));

  // La paleta sigue al tema: si cambiás de oscuro a claro, cambia sola.
  context.subscriptions.push(
    vscode.window.onDidChangeActiveColorTheme(() => applyColors(context, { silent: true }))
  );
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration('ayce.colors')) applyColors(context, { silent: true });
    })
  );

  applyColors(context, { silent: true });
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
  resolveInterpreterTokens,
  buildTerminalCommand,
  buildExecCommand,
  buildRules,
  pickPalette,
  stripRules,
  PALETTES,
};
