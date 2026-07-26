// nl2time bridge: one JSON request on stdin -> one JSON response on stdout.
// Used by the harness both as the backend of the agent-facing time tools
// (nl2time condition) and by scripts/verify_goldens.py as a cross-check.
//
//   {"op":"resolve","phrase":"last week","context":{"now":"...","timeZone":"...","locale":"en-US"}}
//   {"op":"describe","instants":["2026-07-01T02:05:00Z"],"context":{...}}

import { TimeContext, parse, resolve, describe, Temporal } from 'nl2time';

function makeCtx(context) {
  return TimeContext.make({
    now: context.now,
    timeZone: context.timeZone,
    locale: context.locale,
    bias: 'past',
  });
}

function intervalOut(candidate) {
  return {
    start: candidate.start.toString(),
    end: candidate.end.toString(),
    grain: candidate.grain,
  };
}

function handle(req) {
  const ctx = makeCtx(req.context);
  if (req.op === 'resolve') {
    const { matches } = parse(req.phrase, ctx);
    if (matches.length === 0) {
      return { ok: false, error: `No time expression recognized in: ${JSON.stringify(req.phrase)}` };
    }
    const best = matches[0];
    const { candidates } = resolve(best.expr, ctx);
    if (candidates.length === 0) {
      return { ok: false, error: 'Expression recognized but not resolvable' };
    }
    return {
      ok: true,
      interpreted_as: best.text,
      ...intervalOut(candidates[0]),
      alternatives: candidates.slice(1).map(intervalOut),
    };
  }
  if (req.op === 'describe') {
    const phrases = req.instants.map((iso) => {
      const instant = Temporal.Instant.from(iso);
      return {
        instant: iso,
        casual: describe(instant, ctx, { style: 'casual' }).text,
        neutral: describe(instant, ctx).text,
      };
    });
    return { ok: true, phrases };
  }
  return { ok: false, error: `Unknown op: ${req.op}` };
}

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => (input += chunk));
process.stdin.on('end', () => {
  let out;
  try {
    out = handle(JSON.parse(input));
  } catch (err) {
    out = { ok: false, error: String(err && err.message ? err.message : err) };
  }
  process.stdout.write(JSON.stringify(out));
});
