import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Clock3, Eye, EyeOff, Users } from 'lucide-react';
import { useFriendMatch } from '../hooks/useFriendMatch';
import { friendError, friendMatchApi, friendRequestId, uncertainFriendRequest } from '../services/friendMatchApi';
import type { FriendEntity, FriendMode, FriendSnapshot } from '../types/friendMatch';
import GuessInput from '../components/GuessInput';
import QuestionInput from '../components/QuestionInput';
import FriendDuelMap from '../components/friendDuel/FriendDuelMap';
import DuelHistory, { AnswerPicker, PrivateAdvice } from '../components/friendDuel/DuelHistory';
import { duelButton, duelCopy, duelInput, duelModes, duelPanel, duelPrimary } from '../components/friendDuel/copy';
import type { DuelCopy } from '../components/friendDuel/copy';

function Countdown({ deadline, copy }: { deadline: string; copy: DuelCopy }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.ceil((Date.parse(deadline) - now) / 1000));
  return <div className={`flex items-center gap-2 rounded-sm border px-3 py-2 text-sm ${seconds <= 10 ? 'border-amber-400/40 text-amber-200' : 'border-white/10 text-sand-100'}`}>
    <Clock3 size={15} aria-hidden="true" /><span className="sr-only">{copy.deadline}</span>
    <span role="timer" className="font-mono tabular-nums">{seconds > 0 ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}` : copy.expired}</span>
  </div>;
}

function InviteLink({ code, copy }: { code: string; copy: DuelCopy }) {
  const [notice, setNotice] = useState('');
  const link = `${window.location.origin}/duel/${encodeURIComponent(code)}`;
  return <section className={duelPanel} aria-label={copy.invite}>
    <h2 className="flex items-center gap-2 text-sm font-medium"><Users size={16} className="text-emerald-400" />{copy.invite}</h2>
    <label className="sr-only" htmlFor="duel-invite-link">{copy.invite}</label>
    <input id="duel-invite-link" className={`${duelInput} my-3 font-mono text-xs`} value={link} readOnly onFocus={event => event.target.select()} />
    <div className="flex flex-wrap gap-2">
      <button type="button" className={duelPrimary} onClick={() => {
        if (!navigator.clipboard) { setNotice(copy.copyFailed); return; }
        void navigator.clipboard.writeText(link).then(() => setNotice(copy.copied)).catch(() => setNotice(copy.copyFailed));
      }}>{copy.copy}</button>
      {typeof navigator.share === 'function' && <button type="button" className={duelButton} onClick={() => {
        void navigator.share({ title: copy.title, url: link }).catch(cause => {
          if (!(cause instanceof DOMException && cause.name === 'AbortError')) setNotice(copy.copyFailed);
        });
      }}>{copy.share}</button>}
    </div>
    {notice && <p role="status" className="mt-2 text-xs text-emerald-300">{notice}</p>}
    <p className="mt-3 text-xs leading-5 text-zinc-400">{copy.guest}</p>
  </section>;
}

function Results({ snapshot, copy, busy, rematch }: { snapshot: FriendSnapshot; copy: DuelCopy; busy: boolean; rematch: () => void }) {
  const self = snapshot.players.find(player => player.id === snapshot.you);
  const opponent = snapshot.players.find(player => player.id !== snapshot.you);
  const outcome = snapshot.result === 'draw' ? copy.draw : snapshot.winner_id ?
    snapshot.winner_id === snapshot.you ? copy.won : copy.lost :
    snapshot.result === 'interrupted' ? copy.interrupted : copy.cancelled;
  return <section className={`${duelPanel} border-emerald-500/30`} aria-label={copy.results}>
    <p className="font-mono text-[10px] uppercase tracking-widest text-zinc-400">{copy.results}</p>
    <h2 className="mt-2 text-2xl font-semibold text-emerald-300">{outcome}</h2>
    <h3 className="mb-2 mt-4 text-sm font-medium">{copy.reveals}</h3>
    <ul className="space-y-2">{snapshot.reveals?.map(reveal => <li key={reveal.player_id} className="flex flex-wrap justify-between gap-2 text-sm">
      <span className="text-zinc-400">{snapshot.players.find(player => player.id === reveal.player_id)?.name}</span>
      <strong>{reveal.entity.name}</strong>
    </li>)}</ul>
    {snapshot.session_score && <p className="mt-4 text-sm text-zinc-400">
      {copy.wins}: {snapshot.session_score.map(score => `${snapshot.players.find(player => player.id === score.player_id)?.name || '—'} ${score.wins}`).join(' · ')}
      {snapshot.draw_count !== undefined && ` · ${copy.draws}: ${snapshot.draw_count}`}
    </p>}
    <div className="mt-5 flex flex-wrap items-center gap-3">
      {snapshot.rematch_code ? <Link className={duelPrimary} to={`/duel/${encodeURIComponent(snapshot.rematch_code)}`}>{copy.rematchOpen}</Link> :
        snapshot.players.length < 2 ? null : self?.rematch_ready ? <p role="status" className="text-sm text-emerald-300">{copy.rematchWaiting}</p> : <>
          {opponent?.rematch_ready && <p className="w-full text-sm text-emerald-300">{copy.rematchReceived}</p>}
          <button type="button" className={duelPrimary} disabled={busy} onClick={rematch}>{copy.rematch}</button>
        </>}
      <Link className={duelButton} to="/friends">{copy.newDuel}</Link>
    </div>
  </section>;
}

function DuelRoom({ code }: { code?: string }) {
  const { i18n } = useTranslation();
  const copy = duelCopy(i18n.resolvedLanguage || i18n.language);
  const navigate = useNavigate();
  const room = useFriendMatch(code, copy.error, copy.stale);
  const snapshot = room.snapshot;
  const [name, setName] = useState('');
  const [mode, setMode] = useState<FriendMode>(() => {
    const requested = new URLSearchParams(window.location.search).get('mode');
    return duelModes.find(item => item === requested) || 'countrydle';
  });
  const [entryBusy, setEntryBusy] = useState(false);
  const [entryError, setEntryError] = useState('');
  const [entryUncertain, setEntryUncertain] = useState(false);
  const entryRequest = useRef<{ name: string; mode: FriendMode; request_id: string } | null>(null);
  const entryInFlight = useRef(false);
  const [entities, setEntities] = useState<FriendEntity[]>([]);
  const [entitiesError, setEntitiesError] = useState('');
  const [entityReload, setEntityReload] = useState(0);
  const [entitiesLoading, setEntitiesLoading] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const answerPanel = useRef<HTMLElement>(null);
  const activeMode = snapshot?.mode;
  const viewMode = activeMode || room.invite?.mode || mode;
  useEffect(() => {
    if (!activeMode) return;
    let alive = true;
    void (async () => {
      setEntitiesLoading(true); setEntitiesError('');
      try {
        const list = await friendMatchApi.entities(activeMode);
        if (alive) setEntities(list);
      } catch (cause) {
        if (alive) setEntitiesError(friendError(cause, copy.error));
      } finally { if (alive) setEntitiesLoading(false); }
    })();
    return () => { alive = false; };
  }, [activeMode, entityReload, copy.error]);

  const enter = async () => {
    if (entryInFlight.current || (!entryRequest.current && !name.trim())) return;
    entryInFlight.current = true; setEntryBusy(true); setEntryError('');
    const request = entryRequest.current ?? { name: name.trim(), mode, request_id: friendRequestId() };
    entryRequest.current = request;
    try {
      const joined = code ? await friendMatchApi.join(code, { name: request.name, request_id: request.request_id }) : await friendMatchApi.create(request);
      entryRequest.current = null; setEntryUncertain(false);
      room.accept(joined);
      if (!code) navigate(`/duel/${encodeURIComponent(joined.invite_code)}`);
    } catch (cause) {
      const uncertain = uncertainFriendRequest(cause);
      if (!uncertain) entryRequest.current = null;
      setEntryUncertain(uncertain); setEntryError(friendError(cause, copy.error));
      if (code && !uncertain) void room.refresh();
    } finally { entryInFlight.current = false; setEntryBusy(false); }
  };
  const busy = room.busy || room.retryable;
  const self = snapshot?.players.find(player => player.id === snapshot.you);
  const myTurn = snapshot?.status === 'active' && snapshot.active_player_id === snapshot.you;
  const pendingQuestion = snapshot?.history.find(item => item.id === snapshot.pending_question_id);
  const mustAnswer = snapshot?.status === 'active' && snapshot.phase === 'answering' && pendingQuestion?.subject_id === snapshot.you;
  const advice = snapshot?.guidance.find(item => item.question_id === snapshot.pending_question_id);
  const finished = snapshot?.status === 'finished';
  const revealedOpponent = finished ? snapshot.reveals?.find(item => item.player_id !== snapshot.you)?.entity.name : undefined;
  const canGuess = myTurn && (snapshot?.phase === 'thinking' || snapshot?.phase === 'reply');
  useEffect(() => {
    if (mustAnswer && window.innerWidth < 1024) answerPanel.current?.scrollIntoView({ block: 'nearest' });
  }, [mustAnswer, pendingQuestion?.id]);

  return <div className="mx-auto w-full max-w-7xl pb-8">
    <header className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-3">
      <div>
        <p className="mb-1 flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-zinc-400"><Users size={12} aria-hidden="true" />{copy.multiplayer}<span className="text-emerald-400">{snapshot?.status === 'active' ? `${copy.turn} ${snapshot.turn}` : finished ? copy.results : copy.lobby}</span></p>
        <h1 className="text-xl font-semibold tracking-tight text-sand-100 sm:text-2xl">{copy[`play_${viewMode}`]}</h1>
        <p className="mt-1 text-xs text-zinc-400">{copy.turnHelp}</p>
      </div>
      {snapshot && <div className="flex items-center gap-3">
        <span role="status" className={`flex items-center gap-1.5 text-xs ${room.connection === 'connected' ? 'text-emerald-400' : 'text-amber-200'}`}><span className="h-1.5 w-1.5 rounded-full bg-current" />{copy[room.connection]}</span>
        {snapshot.deadline && !finished && <Countdown deadline={snapshot.deadline} copy={copy} />}
      </div>}
    </header>
    {(room.error || room.retryable) && <div role="alert" className="mb-4 space-y-3 rounded-sm border border-red-400/30 bg-red-400/5 p-4 text-sm text-red-200">
      {room.error && <p>{room.error}</p>}{room.retryable && <p>{copy.uncertain}</p>}
      <div className="flex flex-wrap gap-2">{room.retryable && <button type="button" className={duelButton} disabled={room.busy} onClick={() => { void room.retry(); }}>{copy.retry}</button>}
        <button type="button" className={duelButton} onClick={() => { void room.refresh(); }}>{copy.refresh}</button></div>
    </div>}
    {snapshot && <div className="mb-4 grid grid-cols-2 divide-x divide-white/10 overflow-hidden rounded-sm border border-white/10 bg-obsidian-900">
      {snapshot.players.map(player => <section key={player.id} className={`min-w-0 border-b-2 px-3 py-3 sm:px-4 ${snapshot.active_player_id === player.id && !finished ? 'border-emerald-400 bg-emerald-400/5' : 'border-transparent'}`}>
        <div className="flex items-center gap-2"><span className={`h-1.5 w-1.5 shrink-0 rounded-full ${player.connected ? 'bg-emerald-400' : 'bg-zinc-600'}`} title={player.connected ? copy.connected : copy.disconnected} /><h2 className="truncate text-sm font-medium">{player.name}<span className="text-zinc-500">{player.id === snapshot.you ? ` · ${copy.you}` : ''}</span></h2></div>
        <p className="mt-1.5 text-[11px] text-zinc-400">{snapshot.status === 'lobby' ? player.ready ? copy.ready : copy.notReady : `${copy.questions} ${player.question_count} · ${copy.guesses} ${player.guess_count}`}</p>
        {Boolean(player.timeout_count) && <p className="mt-1 text-xs text-amber-200">{copy.timeoutWarning}: {player.timeout_count}</p>}
      </section>)}
      {snapshot.players.length < 2 && <p className="flex items-center px-3 text-xs text-zinc-500">{copy.waitingFriend}</p>}
    </div>}
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(19rem,0.48fr)]">
      <section className="min-w-0 space-y-5" aria-label={copy.atlas}>
        <div className="overflow-hidden rounded-sm border border-white/10 bg-obsidian-900">
          <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-400"><span>{copy.atlas} / {copy[viewMode]}</span><span className="text-emerald-400">{finished ? copy.results : copy.searchArea}</span></div>
          <div className="relative h-[310px] sm:h-[420px] lg:h-[460px]">
            <FriendDuelMap mode={viewMode} matchKey={snapshot?.id || `preview-${viewMode}`} finished={Boolean(finished)} revealedEntityName={revealedOpponent} className="h-full !rounded-none !border-0 !shadow-none" />
          </div>
          <p className="border-t border-white/10 px-4 py-2 text-[11px] text-zinc-500">{copy.mapHelp}</p>
        </div>
        {snapshot?.status === 'lobby' && <section className={duelPanel} aria-label={copy.secret}>
          <div className="mb-3 flex items-center gap-2"><EyeOff size={16} className="text-emerald-400" /><h2 className="text-sm font-medium">{copy.secret}</h2></div>
          <p className="mb-3 text-xs leading-5 text-zinc-400">{copy.secretHelp}</p>
          {snapshot.own_secret && <p className="mb-3 text-lg font-medium text-emerald-300">{snapshot.own_secret.name}</p>}
          {self?.ready ? <button type="button" className={duelButton} disabled={busy} onClick={() => { void room.act('ready', { ready: false }); }}>{copy.unready}</button> : <>
            <GuessInput countries={entities} onGuess={id => room.act('select_secret', { entity_id: id })} isLoading={busy || entitiesLoading} placeholder={copy.search} submitLabel={copy.choose} noMatchesLabel={copy.noMatches} />
            <div className="mt-3 flex flex-wrap gap-2"><button type="button" className={duelButton} disabled={busy} onClick={() => { void room.act('randomize_secret', {}); }}>{copy.random}</button>
              <button type="button" className={duelPrimary} disabled={busy || !snapshot.own_secret} onClick={() => { void room.act('ready', { ready: true }); }}>{copy.ready}</button></div>
          </>}
          <p className="mt-3 text-xs text-zinc-500">{snapshot.players.length < 2 ? copy.waitingFriend : copy.waitingReady}</p>
        </section>}
        {snapshot?.status === 'active' && <>
          {mustAnswer && pendingQuestion ? <section ref={answerPanel} className={`${duelPanel} scroll-mt-24 border-emerald-500/40`}>
            <h2 className="text-sm font-medium text-emerald-300">{copy.answering}</h2>
            <p className="my-4 whitespace-pre-wrap break-words text-lg">{pendingQuestion.question}</p>
            <div className="space-y-4"><AnswerPicker copy={copy} disabled={busy} onAnswer={answer => {
              void room.act('answer', { question_id: pendingQuestion.id, answer, ...(advice?.status === 'completed' ? { observed_ai_question_id: pendingQuestion.id } : {}) });
            }} /><PrivateAdvice guidance={advice} copy={copy} /></div>
          </section> : <section className={duelPanel}>
            <div className="mb-4 flex items-center justify-between gap-3"><h2 className={`text-sm font-medium ${myTurn ? 'text-emerald-300' : 'text-zinc-400'}`}>{myTurn ? copy.yourTurn : snapshot.phase === 'answering' ? copy.awaitingAnswer : copy.theirTurn}</h2></div>
            {snapshot.phase === 'reply' ? <p className="mb-4 text-sm text-amber-200">{copy.reply}</p> : <div>
              <h3 className="mb-2 text-sm text-sand-100">{copy.question}</h3>
              <QuestionInput onAsk={question => room.act('ask', { question: question.trim() })} isLoading={busy} disabled={!myTurn || snapshot.phase !== 'thinking'} placeholder={copy.questionPlaceholder} minLength={3} maxLength={500} />
            </div>}
            <div className="mt-5 border-t border-white/10 pt-4"><h3 className="mb-2 text-sm text-sand-100">{copy.guess}</h3>
              <GuessInput countries={entities} onGuess={id => room.act('guess', { entity_id: id })} isLoading={busy || entitiesLoading} disabled={!canGuess} placeholder={copy.search} noMatchesLabel={copy.noMatches} />
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2"><span className="text-xs text-zinc-500">{copy.turnHelp}</span>{canGuess && <button type="button" className="min-h-10 text-xs text-zinc-400 underline underline-offset-4 hover:text-sand-100 disabled:opacity-40" disabled={busy} onClick={() => { void room.act('pass', {}); }}>{copy.pass}</button>}</div>
          </section>}
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-zinc-400">
            {snapshot.own_secret && <div><button type="button" className="flex min-h-10 items-center gap-2 hover:text-sand-100" aria-expanded={showSecret} onClick={() => setShowSecret(!showSecret)}>{showSecret ? <EyeOff size={15} /> : <Eye size={15} />}{showSecret ? copy.hideSecret : copy.showSecret}</button>{showSecret && <p className="text-emerald-300">{snapshot.own_secret.name}</p>}</div>}
            {snapshot.draw_offer_by === snapshot.you ? <p>{copy.drawOffered}</p> : snapshot.draw_offer_by ? <div className="space-y-2"><p>{copy.drawReceived}</p><div className="flex gap-2"><button type="button" className={duelPrimary} disabled={busy} onClick={() => { void room.act('accept_draw', {}); }}>{copy.acceptDraw}</button><button type="button" className={duelButton} disabled={busy} onClick={() => { void room.act('decline_draw', {}); }}>{copy.declineDraw}</button></div></div> : <button type="button" className="min-h-10 hover:text-sand-100 disabled:opacity-40" disabled={busy} onClick={() => { void room.act('offer_draw', {}); }}>{copy.offerDraw}</button>}
          </div>
        </>}
        {snapshot && finished && <Results snapshot={snapshot} copy={copy} busy={busy} rematch={() => { void room.act('rematch', {}); }} />}
        {snapshot && (entitiesError || (!entitiesLoading && !entities.length)) && !finished && <div role="alert" className="rounded-sm border border-amber-400/30 p-4 text-sm text-amber-200"><p>{entitiesError || copy.noEntities}</p><button type="button" className={`${duelButton} mt-2`} onClick={() => setEntityReload(value => value + 1)}>{copy.refresh}</button></div>}
      </section>
      <aside className="min-w-0 space-y-4" aria-label={copy.title}>
        {room.loading ? <p role="status" className="py-8 text-center text-sm text-emerald-300">{copy.loading}</p> : !snapshot ? <section className={duelPanel}>
          <h2 className="mb-2 text-lg font-medium">{code ? copy.join : copy.multiplayer}</h2><p className="mb-5 text-sm leading-6 text-zinc-400">{copy.subtitle}</p>
          {room.invite && <p className="mb-4 text-sm text-emerald-300">{room.invite.players.map(player => player.name).join(' / ')}</p>}
          {code && !room.invite ? <button type="button" className={duelButton} onClick={() => { void room.refresh(); }}>{copy.refresh}</button> : room.invite?.full || room.invite?.status === 'finished' ? <p className="text-sm text-amber-200">{room.invite.status === 'finished' ? copy.ended : copy.full}</p> : <form className="space-y-4" onSubmit={event => { event.preventDefault(); void enter(); }}>
            <div><label className="mb-2 block text-xs text-zinc-400" htmlFor="duel-name">{copy.name}</label><input id="duel-name" className={duelInput} autoComplete="nickname" value={name} maxLength={40} required disabled={entryBusy || entryUncertain} onChange={event => setName(event.target.value)} /></div>
            {!code && <div><label className="mb-2 block text-xs text-zinc-400" htmlFor="duel-mode">{copy.mode}</label><select id="duel-mode" className={duelInput} value={mode} disabled={entryBusy || entryUncertain} onChange={event => setMode(event.target.value as FriendMode)}>{duelModes.map(item => <option key={item} value={item}>{copy[item]}</option>)}</select></div>}
            {entryError && <p role="alert" className="text-sm text-red-300">{entryError}</p>}{entryUncertain && <p className="text-sm text-amber-200">{copy.uncertain}</p>}
            <button className={`${duelPrimary} w-full`} disabled={entryBusy || !name.trim()}>{entryUncertain ? copy.retry : code ? copy.join : copy.create}</button>
            <p className="text-xs leading-5 text-zinc-400">{copy.guest}</p><p className="text-[11px] leading-5 text-zinc-500">{copy.collection} <Link to="/privacy-policy" className="text-zinc-300 underline underline-offset-2">{copy.privacy}</Link></p>
          </form>}
        </section> : snapshot.status === 'lobby' ? <InviteLink code={snapshot.invite_code} copy={copy} /> : <DuelHistory key={snapshot.id} snapshot={snapshot} copy={copy} busy={busy} correct={(item, answer, observedAiQuestionId) => room.act('correct_answer', { question_id: item.id, answer, expected_revision: item.revision, ...(observedAiQuestionId ? { observed_ai_question_id: observedAiQuestionId } : {}) })} />}
        <details className={duelPanel}><summary className="cursor-pointer text-sm font-medium">{copy.rulesTitle}</summary><p className="mt-3 text-xs leading-6 text-zinc-400">{copy.rules}</p><p className="mt-3 text-xs leading-6 text-zinc-400">{copy.timeoutRules}</p></details>
        {snapshot && !finished && <button type="button" className="min-h-10 text-xs text-zinc-500 underline underline-offset-4 hover:text-red-300 disabled:opacity-40" disabled={busy} onClick={() => { if (window.confirm(copy.leaveConfirm)) void room.act('leave', {}); }}>{copy.leave}</button>}
      </aside>
    </div>
  </div>;
}

export default function DuelPage() {
  const { code } = useParams<{ code: string }>();
  return <DuelRoom key={code || 'create'} code={code} />;
}
