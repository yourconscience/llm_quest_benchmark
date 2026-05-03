const {
  useState,
  useEffect,
  useRef
} = React;

// ---- Tag parser (ported from space-rangers-quest) ----

const SIMPLE_TAGS = ['clr', 'clrEnd', '/clr', 'fix', '/fix', '/format', '/color'];
function splitStringToTokens(str) {
  const out = [];
  let pos = 0;
  let text = '';
  const flushText = () => {
    if (text.length > 0) {
      out.push({
        type: 'text',
        text
      });
      text = '';
    }
  };
  while (pos < str.length) {
    let found = false;
    for (const tag of SIMPLE_TAGS) {
      const candidate = '<' + tag + '>';
      if (str.slice(pos, pos + candidate.length) === candidate) {
        flushText();
        out.push({
          type: 'tag',
          tag
        });
        pos += candidate.length;
        found = true;
        break;
      }
    }
    if (found) continue;
    const formatMatch = str.slice(pos).match(/^<format=?(left|right|center)?,?(\d+)?>/);
    if (formatMatch) {
      flushText();
      pos += formatMatch[0].length;
      const kind = formatMatch[1];
      const n = formatMatch[2] ? parseInt(formatMatch[2]) : undefined;
      out.push({
        type: 'format',
        format: kind && n !== undefined ? {
          kind,
          numberOfSpaces: n
        } : undefined
      });
      continue;
    }
    const colorMatch = str.slice(pos).match(/^<color=?(\d+)?,?(\d+)?,?(\d+)?>/);
    if (colorMatch) {
      flushText();
      pos += colorMatch[0].length;
      const r = colorMatch[1] ? parseInt(colorMatch[1]) : undefined;
      const g = colorMatch[2] ? parseInt(colorMatch[2]) : undefined;
      const b = colorMatch[3] ? parseInt(colorMatch[3]) : undefined;
      out.push({
        type: 'color',
        color: r !== undefined && g !== undefined && b !== undefined ? {
          r,
          g,
          b
        } : undefined
      });
      continue;
    }
    text += str[pos];
    pos++;
  }
  flushText();
  return out;
}
function formatTokens(parsed) {
  const out = [];
  let clrCount = 0;
  let fixCount = 0;
  let format = undefined;
  let color = undefined;
  for (const token of parsed) {
    if (token.type === 'text') {
      token.text.split(/\r\n|\n/).forEach((line, index, arr) => {
        const haveNext = index !== arr.length - 1;
        out.push({
          type: 'text',
          text: line,
          isClr: clrCount > 0 || undefined,
          isFix: fixCount > 0 || undefined,
          color
        });
        if (haveNext) out.push({
          type: 'newline',
          isFix: fixCount > 0 || undefined
        });
      });
    } else if (token.type === 'format') {
      if (!format && token.format) format = {
        format: token.format,
        startedAt: out.length
      };
    } else if (token.type === 'color') {
      if (!color && token.color) color = token.color;
    } else if (token.type === 'tag') {
      const tag = token.tag;
      if (tag === '/color') {
        color = undefined;
      } else if (tag === 'fix') {
        fixCount++;
      } else if (tag === '/fix') {
        fixCount--;
      } else if (tag === 'clr') {
        clrCount++;
      } else if (tag === 'clrEnd' || tag === '/clr') {
        clrCount--;
      } else if (tag === '/format') {
        if (format) {
          let length = 0;
          for (const t of out.slice(format.startedAt)) {
            length += t.type === 'text' ? t.text.length : 0;
          }
          const padNeeded = Math.max(0, format.format.numberOfSpaces - length);
          const leftPad = padNeeded ? format.format.kind === 'left' ? ' '.repeat(padNeeded) : format.format.kind === 'center' ? ' '.repeat(Math.floor(padNeeded / 2)) : '' : '';
          const rightPad = padNeeded ? format.format.kind === 'right' ? ' '.repeat(padNeeded) : format.format.kind === 'center' ? ' '.repeat(Math.ceil(padNeeded / 2)) : '' : '';
          if (leftPad) out.splice(format.startedAt, 0, {
            type: 'text',
            text: leftPad,
            isClr: clrCount > 0 || undefined,
            isFix: fixCount > 0 || undefined
          });
          if (rightPad) out.push({
            type: 'text',
            text: rightPad,
            isClr: clrCount > 0 || undefined,
            isFix: fixCount > 0 || undefined
          });
        }
        format = undefined;
      }
    }
  }
  return out;
}
function QuestTags({
  str
}) {
  const nbsp = ' ';
  const tokens = formatTokens(splitStringToTokens(str || ''));
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", null, nbsp), tokens.map((tok, i) => {
    if (tok.type === 'newline') {
      return /*#__PURE__*/React.createElement("span", {
        key: i
      }, /*#__PURE__*/React.createElement("br", null), nbsp);
    }
    const style = tok.color ? {
      color: `rgb(${tok.color.r},${tok.color.g},${tok.color.b})`
    } : undefined;
    const cls = [tok.isClr ? 'game-clr' : '', tok.isFix ? 'game-fix' : ''].filter(Boolean).join(' ') || undefined;
    return /*#__PURE__*/React.createElement("span", {
      key: i,
      className: cls,
      style: style
    }, tok.text);
  }));
}

// ---- Helpers ----

function normalizeChoice(text) {
  return String(text == null ? '' : text).replace(/<clr>|<clrEnd>|<\/clr>/g, '').trim().toLowerCase();
}
function stripClr(s) {
  return String(s == null ? '' : s).replace(/<clr>|<clrEnd>|<\/clr>/g, '');
}
function diffColor(diff) {
  if (diff === 'easy') return 'var(--green)';
  if (diff === 'medium') return 'var(--orange)';
  return 'var(--red)';
}
function diffLabel(diff) {
  return diff.charAt(0).toUpperCase() + diff.slice(1);
}
function sortQuests(quests) {
  const order = {
    easy: 0,
    medium: 1,
    hard: 2
  };
  return [...quests].sort((a, b) => {
    const da = order[a.difficulty] ?? 3;
    const db = order[b.difficulty] ?? 3;
    return da !== db ? da - db : a.title.localeCompare(b.title);
  });
}
const PLAY_URL = 'https://yourconscience.github.io/llm_quest_benchmark/play.html';
const SHARE_FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif';
function drawTextLine(ctx, text, x, y, maxWidth) {
  ctx.fillText(text, x, y, maxWidth);
}

// ---- CohortBars (reusable distribution bars) ----

function CohortBars({
  cohortLoc,
  playerChoiceNorm,
  activeFamily,
  onFamilyChange,
  families
}) {
  if (!cohortLoc || cohortLoc.n < 5) {
    return /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--muted)',
        fontSize: '0.85rem'
      }
    }, "Insufficient data for this location.");
  }
  const choices = cohortLoc.choices || {};
  let total = 0;
  Object.values(choices).forEach(data => {
    const n = activeFamily === 'all' ? data.n || 0 : data.n_by_family && data.n_by_family[activeFamily] != null ? data.n_by_family[activeFamily] : 0;
    total += n;
  });
  const displayN = activeFamily === 'all' ? cohortLoc.n : total;
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: '0.75rem',
      flexWrap: 'wrap',
      gap: '0.5rem'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: '0.82rem',
      color: 'var(--muted)'
    }
  }, "AI models chose (", displayN, " runs)"), families.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: '0.4rem',
      flexWrap: 'wrap'
    }
  }, ['all', ...families].map(fam => /*#__PURE__*/React.createElement("button", {
    key: fam,
    className: 'family-pill' + (fam === activeFamily ? ' active' : ''),
    onClick: e => {
      e.stopPropagation();
      onFamilyChange(fam);
    }
  }, fam === 'all' ? 'All' : fam)))), /*#__PURE__*/React.createElement("div", null, Object.entries(choices).map(([key, data]) => {
    const isPlayer = normalizeChoice(key) === normalizeChoice(playerChoiceNorm || '');
    const n = activeFamily === 'all' ? data.n || 0 : data.n_by_family && data.n_by_family[activeFamily] != null ? data.n_by_family[activeFamily] : 0;
    const pct = total > 0 ? Math.round(n / total * 100) : 0;
    return /*#__PURE__*/React.createElement("div", {
      key: key,
      className: 'cohort-row' + (isPlayer ? ' player-choice' : '')
    }, /*#__PURE__*/React.createElement("div", {
      className: "cohort-label"
    }, data.text || key), /*#__PURE__*/React.createElement("div", {
      className: "cohort-bar-wrap"
    }, /*#__PURE__*/React.createElement("div", {
      className: "success-bar"
    }, /*#__PURE__*/React.createElement("div", {
      className: "success-fill",
      style: {
        width: pct + '%'
      }
    })), /*#__PURE__*/React.createElement("span", {
      className: "cohort-pct"
    }, pct, "%")));
  })));
}

// ---- DecisionHistory ----

function DecisionHistory({
  path,
  families
}) {
  const [openIdx, setOpenIdx] = useState(null);
  const [activeFamily, setActiveFamily] = useState('all');
  const branchingSteps = path.filter(entry => entry.cohortLoc);
  if (branchingSteps.length === 0) return null;
  return /*#__PURE__*/React.createElement("div", {
    className: "history-section"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: '0.78rem',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      color: 'var(--muted)',
      marginBottom: '0.5rem'
    }
  }, "Decision History"), branchingSteps.map((entry, i) => {
    const isOpen = openIdx === i;
    return /*#__PURE__*/React.createElement("div", {
      key: i,
      className: 'history-item' + (isOpen ? ' open' : '')
    }, /*#__PURE__*/React.createElement("div", {
      className: "history-header",
      onClick: () => setOpenIdx(isOpen ? null : i)
    }, /*#__PURE__*/React.createElement("span", {
      className: "history-step"
    }, "#", entry.step), /*#__PURE__*/React.createElement("span", {
      className: "history-choice"
    }, entry.choiceText), /*#__PURE__*/React.createElement("span", {
      className: "history-agree",
      style: {
        color: entry.agreed ? 'var(--green)' : entry.agreed === false ? 'var(--red)' : 'var(--muted)'
      }
    }, entry.agreed === true ? 'AI agreed' : entry.agreed === false ? 'AI disagreed' : ''), /*#__PURE__*/React.createElement("span", {
      className: "history-chevron"
    }, "\u25B6")), isOpen && /*#__PURE__*/React.createElement("div", {
      className: "cohort-inline"
    }, /*#__PURE__*/React.createElement(CohortBars, {
      cohortLoc: entry.cohortLoc,
      playerChoiceNorm: entry.playerChoiceNorm,
      activeFamily: activeFamily,
      onFamilyChange: setActiveFamily,
      families: families
    })));
  }));
}

// ---- Share card renderer ----

function renderShareCard(questTitle, outcomeLabel, steps, aiAgreeRate, cohortWinRate) {
  const W = 640,
    H = 400;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');

  // Background
  ctx.fillStyle = '#0d1117';
  ctx.fillRect(0, 0, W, H);

  // Border glow
  ctx.strokeStyle = '#30363d';
  ctx.lineWidth = 2;
  ctx.strokeRect(1, 1, W - 2, H - 2);

  // Accent line at top
  const accentColor = outcomeLabel === 'SUCCESS' ? '#3fb950' : '#f85149';
  ctx.fillStyle = accentColor;
  ctx.fillRect(0, 0, W, 4);

  // Quest title
  ctx.fillStyle = '#e6edf3';
  ctx.font = 'bold 22px ' + SHARE_FONT;
  drawTextLine(ctx, questTitle, 40, 52, W - 80);

  // Outcome badge
  const badgeY = 80;
  ctx.font = 'bold 28px ' + SHARE_FONT;
  const badgeText = outcomeLabel;
  const badgeW = ctx.measureText(badgeText).width + 40;
  const badgeH = 44;
  ctx.fillStyle = accentColor;
  roundRect(ctx, 40, badgeY, badgeW, badgeH, 8);
  ctx.fill();
  ctx.fillStyle = outcomeLabel === 'SUCCESS' ? '#0d1117' : '#fff';
  ctx.fillText(badgeText, 60, badgeY + 32);

  // Stats grid
  const statsY = 160;
  const stats = [{
    value: String(steps),
    label: 'steps'
  }, {
    value: aiAgreeRate + '%',
    label: 'AI agreed'
  }];
  if (cohortWinRate != null) {
    stats.push({
      value: Math.round(cohortWinRate * 100) + '%',
      label: 'AI win rate'
    });
  }
  const colW = (W - 80) / stats.length;
  stats.forEach((s, i) => {
    const x = 40 + i * colW;
    // Value
    ctx.fillStyle = '#58a6ff';
    ctx.font = 'bold 36px ' + SHARE_FONT;
    ctx.fillText(s.value, x, statsY);
    // Label
    ctx.fillStyle = '#8b949e';
    ctx.font = '14px ' + SHARE_FONT;
    ctx.fillText(s.label, x, statsY + 24);
  });

  // Divider
  ctx.fillStyle = '#30363d';
  ctx.fillRect(40, statsY + 50, W - 80, 1);

  // Comparison text
  const compY = statsY + 85;
  if (cohortWinRate != null) {
    const humanWon = outcomeLabel === 'SUCCESS';
    const aiPct = Math.round(cohortWinRate * 100);
    let compText;
    if (humanWon && aiPct < 50) compText = 'Beat the AI cohort!';else if (humanWon) compText = 'Won alongside ' + aiPct + '% of AI models';else if (aiPct < 20) compText = 'Even AI struggles - only ' + aiPct + '% win rate';else compText = 'AI cohort wins ' + aiPct + '% of the time';
    ctx.fillStyle = '#c9d1d9';
    ctx.font = '16px ' + SHARE_FONT;
    drawTextLine(ctx, compText, 40, compY, W - 80);
  }

  // Footer
  ctx.fillStyle = '#30363d';
  ctx.fillRect(0, H - 50, W, 1);
  ctx.fillStyle = '#8b949e';
  ctx.font = '13px ' + SHARE_FONT;
  ctx.fillText('LLM-Quest Benchmark', 40, H - 20);
  ctx.fillStyle = '#58a6ff';
  ctx.font = '13px ' + SHARE_FONT;
  const url = PLAY_URL.replace('https://', '');
  drawTextLine(ctx, url, W - 40 - ctx.measureText(url).width, H - 20, W - 80);
  return canvas;
}
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}
function makeShareText(questTitle, outcomeLabel) {
  const verb = outcomeLabel === 'SUCCESS' ? 'beat' : 'tried';
  return 'I ' + verb + ' "' + questTitle + '" on LLM-Quest Benchmark. Can you do better?';
}
function downloadCanvas(canvas, filename) {
  const link = document.createElement('a');
  link.download = filename;
  link.href = canvas.toDataURL('image/png');
  link.click();
}
async function copyShareText(text, url) {
  if (!navigator.clipboard || !navigator.clipboard.writeText) return false;
  await navigator.clipboard.writeText(text + '\n' + url);
  return true;
}
async function shareResult(canvas, questTitle, outcomeLabel) {
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
  const file = new File([blob], 'quest-result.png', {
    type: 'image/png'
  });
  const url = PLAY_URL;
  const shareData = {
    title: questTitle + ' - ' + outcomeLabel,
    text: makeShareText(questTitle, outcomeLabel),
    url,
    files: [file]
  };
  if (navigator.canShare && navigator.canShare(shareData)) {
    await navigator.share(shareData);
    return 'Shared result image.';
  }
  if (navigator.share) {
    await navigator.share({
      title: shareData.title,
      text: shareData.text,
      url: shareData.url
    });
    downloadCanvas(canvas, 'quest-result.png');
    return 'Shared link and downloaded result image.';
  }
  const copied = await copyShareText(shareData.text, shareData.url).catch(() => false);
  downloadCanvas(canvas, 'quest-result.png');
  return copied ? 'Copied share text and downloaded result image.' : 'Downloaded result image. Attach it to your social post.';
}

// ---- EndScreen ----

function EndScreen({
  outcome,
  cohortWinRate,
  path,
  questTitle,
  onPlayAgain,
  onTryAnother
}) {
  const [shareStatus, setShareStatus] = useState('');
  const outcomeLabel = {
    win: 'SUCCESS',
    fail: 'FAILURE',
    dead: 'DEAD'
  }[outcome] || 'FAILURE';
  const branchingSteps = path.filter(e => e.agreed !== null);
  const agreeCount = branchingSteps.filter(e => e.agreed === true).length;
  const aiAgreeRate = branchingSteps.length > 0 ? Math.round(agreeCount / branchingSteps.length * 100) : 0;
  function handleShare() {
    setShareStatus('Preparing share card...');
    const canvas = renderShareCard(questTitle, outcomeLabel, path.length, aiAgreeRate, cohortWinRate);
    shareResult(canvas, questTitle, outcomeLabel).then(status => setShareStatus(status)).catch(() => setShareStatus('Sharing failed. Try downloading from another browser.'));
  }
  return /*#__PURE__*/React.createElement("div", {
    className: "container py-5 text-center",
    style: {
      maxWidth: 700
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: 'outcome-badge outcome-' + outcomeLabel,
    style: {
      display: 'inline-block',
      marginBottom: '1rem'
    }
  }, outcomeLabel), cohortWinRate != null && /*#__PURE__*/React.createElement("p", {
    style: {
      color: 'var(--muted)',
      marginBottom: '1.5rem'
    }
  }, "AI cohort: ", Math.round(cohortWinRate * 100), "% won this quest."), /*#__PURE__*/React.createElement("h5", {
    style: {
      textAlign: 'left',
      marginBottom: '0.5rem'
    }
  }, "Your path"), /*#__PURE__*/React.createElement("div", {
    className: "card-table",
    style: {
      marginBottom: '1.5rem'
    }
  }, /*#__PURE__*/React.createElement("table", {
    className: "table table-sm path-table"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "Step"), /*#__PURE__*/React.createElement("th", null, "Choice"), /*#__PURE__*/React.createElement("th", null, "AI agreed?"))), /*#__PURE__*/React.createElement("tbody", null, path.map((entry, i) => /*#__PURE__*/React.createElement("tr", {
    key: i
  }, /*#__PURE__*/React.createElement("td", {
    style: {
      color: 'var(--muted)'
    }
  }, entry.step), /*#__PURE__*/React.createElement("td", null, entry.choiceText), /*#__PURE__*/React.createElement("td", null, entry.agreed === true && /*#__PURE__*/React.createElement("span", {
    className: "agree-yes"
  }, "Yes"), entry.agreed === false && /*#__PURE__*/React.createElement("span", {
    className: "agree-no"
  }, "No"), entry.agreed === null && /*#__PURE__*/React.createElement("span", {
    className: "agree-no"
  }, "-"))))))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: '0.75rem',
      justifyContent: 'center',
      flexWrap: 'wrap'
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn btn-primary",
    onClick: onPlayAgain
  }, "Play Again"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-outline-secondary",
    onClick: onTryAnother
  }, "Try Another Quest"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-outline-info",
    onClick: handleShare
  }, "Share Result")), shareStatus && /*#__PURE__*/React.createElement("p", {
    style: {
      color: 'var(--muted)',
      fontSize: '0.9rem',
      marginTop: '0.75rem'
    }
  }, shareStatus));
}

// ---- QuestPlay ----

function QuestPlay({
  quest,
  cohortData,
  onQuit
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [player, setPlayer] = useState(null);
  const [canonicalPlayer, setCanonicalPlayer] = useState(null);
  const [gameState, setGameState] = useState(null);
  const [stepHistory, setStepHistory] = useState([]);
  const [stepNum, setStepNum] = useState(0);
  const [path, setPath] = useState([]);
  const [ended, setEnded] = useState(null);
  const [obsKey, setObsKey] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetch('play/quests/' + quest.id + '.qm.gz', {
      signal: controller.signal
    }).then(r => r.arrayBuffer()).then(buf => {
      const ungzipped = pako.ungzip(new Uint8Array(buf));
      const qm = QMEngine.parse(Buffer.from(ungzipped));
      const p = new QMEngine.QMPlayer(qm, questEngineLang(quest));
      p.start();
      return loadCanonicalPlayer(quest, p, controller.signal).then(canonical => ({
        p,
        canonical
      }));
    }).then(({
      p,
      canonical
    }) => {
      setPlayer(p);
      setCanonicalPlayer(canonical);
      setGameState(p.getState());
      setStepNum(1);
      setLoading(false);
    }).catch(err => {
      if (err.name === 'AbortError') return;
      setError('Failed to load quest: ' + err.message);
      setLoading(false);
    });
    return () => controller.abort();
  }, [quest.id]);
  const families = cohortData && cohortData.model_families || [];
  function getCohortLoc(locationId) {
    if (!cohortData || !cohortData.locations) return null;
    return cohortData.locations[String(locationId)] || null;
  }
  function getMajorityChoice(cohortLoc) {
    const choices = cohortLoc.choices || {};
    let bestKey = null,
      bestVal = -1;
    Object.entries(choices).forEach(([key, data]) => {
      const val = data.dist && data.dist.all != null ? data.dist.all : 0;
      if (val > bestVal) {
        bestVal = val;
        bestKey = key;
      }
    });
    return bestKey;
  }
  function canonicalChoiceNorm(choice) {
    if (!canonicalPlayer) return normalizeChoice(choice.text);
    const canonicalState = canonicalPlayer.getState();
    const canonicalChoice = (canonicalState.choices || []).find(c => c.jumpId === choice.jumpId);
    return normalizeChoice(canonicalChoice && canonicalChoice.text || choice.text);
  }
  function handleChoice(choice, activeChoices) {
    const locationId = player.getSaving().locationId;
    const choiceNorm = canonicalChoiceNorm(choice);
    const cohortLoc = getCohortLoc(locationId);
    const isBranching = activeChoices.length >= 2;
    const majority = isBranching && cohortLoc ? getMajorityChoice(cohortLoc) : null;
    const agreed = majority ? normalizeChoice(majority) === choiceNorm : null;
    setPath(prev => [...prev, {
      step: stepNum,
      choiceText: stripClr(choice.text),
      agreed: isBranching ? agreed : null,
      cohortLoc: isBranching ? cohortLoc : null,
      playerChoiceNorm: isBranching ? choiceNorm : null
    }]);
    setStepHistory(prev => [...prev, {
      player: player.getSaving(),
      canonicalPlayer: canonicalPlayer ? canonicalPlayer.getSaving() : null
    }]);
    player.performJump(choice.jumpId);
    if (canonicalPlayer) canonicalPlayer.performJump(choice.jumpId);
    const nextState = player.getState();
    const gs = nextState.gameState;
    const isTerminal = gs === 'win' || gs === 'fail' || gs === 'dead';
    if (isTerminal) {
      setEnded(gs);
    } else {
      setGameState(player.getState());
      setStepNum(n => n + 1);
      setObsKey(k => k + 1);
    }
  }
  function handleBack() {
    if (stepHistory.length === 0) return;
    const prevSaving = stepHistory[stepHistory.length - 1];
    player.loadSaving(prevSaving.player || prevSaving);
    if (canonicalPlayer && prevSaving.canonicalPlayer) {
      canonicalPlayer.loadSaving(prevSaving.canonicalPlayer);
    }
    setStepHistory(prev => prev.slice(0, -1));
    setGameState(player.getState());
    setStepNum(n => Math.max(1, n - 1));
    setPath(prev => prev.slice(0, -1));
    setObsKey(k => k + 1);
    setEnded(null);
  }
  if (loading) {
    return /*#__PURE__*/React.createElement("div", {
      className: "spinner-wrap"
    }, /*#__PURE__*/React.createElement("div", {
      className: "spinner-border text-secondary",
      role: "status"
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--muted)'
      }
    }, "Loading quest..."));
  }
  if (error) {
    return /*#__PURE__*/React.createElement("div", {
      className: "container py-5",
      style: {
        maxWidth: 700,
        textAlign: 'center'
      }
    }, /*#__PURE__*/React.createElement("p", {
      style: {
        color: 'var(--red)'
      }
    }, error), /*#__PURE__*/React.createElement("button", {
      className: "btn btn-outline-secondary",
      onClick: onQuit
    }, "Back to quests"));
  }
  if (ended) {
    return /*#__PURE__*/React.createElement(EndScreen, {
      outcome: ended,
      cohortWinRate: cohortData ? cohortData.win_rate : null,
      path: path,
      questTitle: quest.title || quest.id,
      onPlayAgain: () => {
        player.start();
        if (canonicalPlayer) canonicalPlayer.loadSaving(player.getSaving());
        setGameState(player.getState());
        setStepNum(1);
        setPath([]);
        setStepHistory([]);
        setEnded(null);
        setObsKey(k => k + 1);
      },
      onTryAnother: onQuit
    });
  }
  if (!gameState) return null;
  const choices = gameState.choices || [];
  const activeChoices = choices.filter(c => c.active);
  const params = (gameState.paramsState || []).filter(p => p && p.trim());
  return /*#__PURE__*/React.createElement("div", {
    className: "container py-4",
    style: {
      maxWidth: 800
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: '1rem'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h4", {
    style: {
      marginBottom: 0
    }
  }, quest.title), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--muted)',
      fontSize: '0.85rem'
    }
  }, "Step ", stepNum)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: '0.5rem'
    }
  }, stepHistory.length > 0 && /*#__PURE__*/React.createElement("button", {
    className: "btn btn-sm btn-outline-secondary",
    onClick: handleBack
  }, "\u2190 Back"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-sm btn-outline-secondary",
    onClick: onQuit
  }, "Quit"))), params.length > 0 && /*#__PURE__*/React.createElement("div", {
    className: "params-strip"
  }, params.map((p, i) => /*#__PURE__*/React.createElement("span", {
    key: i,
    className: "param-pill"
  }, /*#__PURE__*/React.createElement(QuestTags, {
    str: p
  })))), /*#__PURE__*/React.createElement("div", {
    key: obsKey,
    className: "obs-panel"
  }, /*#__PURE__*/React.createElement(QuestTags, {
    str: gameState.text || ''
  })), /*#__PURE__*/React.createElement("div", null, choices.map((choice, i) => /*#__PURE__*/React.createElement("button", {
    key: i,
    className: 'choice-btn' + (choice.active ? '' : ' inactive'),
    disabled: !choice.active,
    onClick: () => choice.active && handleChoice(choice, activeChoices)
  }, /*#__PURE__*/React.createElement(QuestTags, {
    str: choice.text || ''
  })))), /*#__PURE__*/React.createElement(DecisionHistory, {
    path: path,
    families: families
  }));
}

// ---- Language helpers ----

function questEngineLang(quest) {
  return quest.lang === 'ru' ? 'rus' : 'eng';
}
function loadCanonicalPlayer(quest, player, signal) {
  if (!quest.canonical_id || quest.canonical_id === quest.id) {
    return Promise.resolve(null);
  }
  return fetch('play/quests/' + quest.canonical_id + '.qm.gz', {
    signal
  }).then(r => r.ok ? r.arrayBuffer() : null).then(buf => {
    if (!buf) return null;
    const ungzipped = pako.ungzip(new Uint8Array(buf));
    const qm = QMEngine.parse(Buffer.from(ungzipped));
    const canonical = new QMEngine.QMPlayer(qm, 'eng');
    canonical.loadSaving(player.getSaving());
    return canonical;
  }).catch(() => null);
}

// ---- QuestSelect ----

function QuestSelect({
  onSelectQuest,
  lang,
  onLangChange
}) {
  const [quests, setQuests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  useEffect(() => {
    fetch('play/quest-index.json').then(r => r.json()).then(data => {
      setQuests(sortQuests(data.quests || []));
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);
  const filtered = quests.filter(q => {
    if (q.lang && q.lang !== lang) return false;
    if (!q.lang && lang !== 'en') return false;
    if (search && !q.title.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });
  return /*#__PURE__*/React.createElement("div", {
    className: "container py-5",
    style: {
      maxWidth: 860
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: '1.5rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: '0.75rem'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", {
    style: {
      marginBottom: '0.25rem'
    }
  }, "Play a Quest"), /*#__PURE__*/React.createElement("p", {
    style: {
      color: 'var(--muted)',
      marginBottom: 0
    }
  }, "Pick a quest, make your choices, then see what AI models chose at each decision point.")), /*#__PURE__*/React.createElement("div", {
    className: "lang-toggle"
  }, ['en', 'ru'].map(l => /*#__PURE__*/React.createElement("button", {
    key: l,
    className: 'lang-pill' + (l === lang ? ' active' : ''),
    onClick: () => onLangChange(l)
  }, l.toUpperCase())))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: '1.5rem'
    }
  }, /*#__PURE__*/React.createElement("input", {
    className: "search-input",
    type: "text",
    placeholder: "Search quests...",
    value: search,
    onChange: e => setSearch(e.target.value)
  })), loading ? /*#__PURE__*/React.createElement("div", {
    className: "spinner-wrap"
  }, /*#__PURE__*/React.createElement("div", {
    className: "spinner-border text-secondary",
    role: "status"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--muted)'
    }
  }, "Loading quests...")) : /*#__PURE__*/React.createElement("div", {
    className: "row g-3"
  }, filtered.map(q => /*#__PURE__*/React.createElement("div", {
    key: q.id,
    className: "col-md-4 col-sm-6"
  }, /*#__PURE__*/React.createElement("div", {
    className: "quest-card h-100",
    style: {
      display: 'flex',
      flexDirection: 'column'
    },
    onClick: () => onSelectQuest(q)
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: '0.5rem'
    }
  }, /*#__PURE__*/React.createElement("h5", {
    style: {
      margin: 0
    }
  }, q.title), /*#__PURE__*/React.createElement("span", {
    className: "diff-badge",
    style: {
      color: diffColor(q.difficulty)
    }
  }, diffLabel(q.difficulty))), /*#__PURE__*/React.createElement("p", {
    style: {
      color: 'var(--muted)',
      fontSize: '0.88rem',
      marginBottom: '0.5rem',
      flexGrow: 1
    }
  }, q.description), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: '0.82rem',
      color: 'var(--muted)',
      marginBottom: '0.25rem'
    }
  }, "~", q.stepsRange, " steps"), q.win_rate != null ? /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: '0.82rem',
      color: 'var(--muted)',
      marginBottom: '0.75rem'
    }
  }, "AI win rate: ", Math.round((q.win_rate || 0) * 100), "%") : /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: '0.82rem',
      color: 'var(--muted)',
      marginBottom: '0.75rem'
    }
  }, "No AI data yet"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn-sm btn-outline-primary",
    style: {
      marginTop: 'auto'
    },
    onClick: e => {
      e.stopPropagation();
      onSelectQuest(q);
    }
  }, "Play")))), filtered.length === 0 && /*#__PURE__*/React.createElement("div", {
    className: "col-12",
    style: {
      color: 'var(--muted)',
      textAlign: 'center',
      padding: '2rem'
    }
  }, "No quests found.")));
}

// ---- App ----

function App() {
  const [screen, setScreen] = useState('select');
  const [selectedQuest, setSelectedQuest] = useState(null);
  const [cohortData, setCohortData] = useState(null);
  const [lang, setLang] = useState('en');
  const cohortReqSeq = useRef(0);
  function handleSelectQuest(quest) {
    const reqId = ++cohortReqSeq.current;
    setSelectedQuest(quest);
    setCohortData(null);
    setScreen('play');
    const cohortId = quest.canonical_id || quest.id;
    fetch('play/' + cohortId + '.json').then(r => r.ok ? r.json() : null).then(data => {
      if (cohortReqSeq.current === reqId) setCohortData(data);
    }).catch(() => {
      if (cohortReqSeq.current === reqId) setCohortData(null);
    });
  }
  if (screen === 'select') {
    return /*#__PURE__*/React.createElement(QuestSelect, {
      onSelectQuest: handleSelectQuest,
      lang: lang,
      onLangChange: setLang
    });
  }
  return /*#__PURE__*/React.createElement(QuestPlay, {
    quest: selectedQuest,
    cohortData: cohortData,
    onQuit: () => setScreen('select')
  });
}
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(/*#__PURE__*/React.createElement(App, null));
