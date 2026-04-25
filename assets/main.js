const state = {
  view: 'tributos',
  displayMode: 'list',
  monthIndex: 0,
  selectedDay: null,
  query: '',
  months: [],
  payload: null,
};

const PT_MONTH_TO_NUM = {
  janeiro: 1,
  fevereiro: 2,
  marco: 3,
  abril: 4,
  maio: 5,
  junho: 6,
  julho: 7,
  agosto: 8,
  setembro: 9,
  outubro: 10,
  novembro: 11,
  dezembro: 12,
};

const PT_MONTH_LABEL = {
  1: 'Janeiro',
  2: 'Fevereiro',
  3: 'Março',
  4: 'Abril',
  5: 'Maio',
  6: 'Junho',
  7: 'Julho',
  8: 'Agosto',
  9: 'Setembro',
  10: 'Outubro',
  11: 'Novembro',
  12: 'Dezembro',
};

const WEEKDAYS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];

const monthSelect = document.getElementById('month-select');
const searchInput = document.getElementById('search-input');
const tableHead = document.getElementById('table-head');
const tableBody = document.getElementById('table-body');
const summary = document.getElementById('summary');
const sourceLinks = document.getElementById('source-links');
const tablePanel = document.getElementById('table-panel');
const calendarPanel = document.getElementById('calendar-panel');
const calendarHeader = document.getElementById('calendar-header');
const calendarGrid = document.getElementById('calendar-grid');
const calendarDaily = document.getElementById('calendar-daily');
const calendarDetails = document.getElementById('calendar-details');

function normalizeText(value) {
  return (value ?? '')
    .toString()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase();
}

function escapeHtml(value) {
  return (value ?? '')
    .toString()
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function truncate(text, max = 80) {
  const safe = (text ?? '').toString().trim();
  if (safe.length <= max) {
    return safe;
  }
  return `${safe.slice(0, max - 1)}…`;
}

function formatDueDay(item) {
  if (state.view === 'tributos' && item.due_type === 'daily') {
    return '<span class="badge">Diário</span>';
  }
  return escapeHtml(item.due_day ?? '-');
}

function getCurrentTypeLabel() {
  return state.view === 'tributos' ? 'Tributos' : 'Declarações';
}

function renderSummary() {
  if (!state.payload) {
    summary.innerHTML = '';
    return;
  }

  const counts = state.payload.counts || {};
  const comp = state.payload.competence || {};
  const agendaPeriod = inferAgendaPeriod();
  summary.innerHTML = `
    <article class="summary-card">
      <p class="summary-card__label">Competência fiscal</p>
      <p class="summary-card__value">${escapeHtml(comp.label || 'Não identificada')}</p>
    </article>
    <article class="summary-card">
      <p class="summary-card__label">Mês da agenda</p>
      <p class="summary-card__value">${escapeHtml(agendaPeriod?.label || 'Não identificado')}</p>
    </article>
    <article class="summary-card">
      <p class="summary-card__label">Tributos</p>
      <p class="summary-card__value">${escapeHtml(counts.tributos ?? 0)}</p>
    </article>
    <article class="summary-card">
      <p class="summary-card__label">Declarações</p>
      <p class="summary-card__value">${escapeHtml(counts.declaracoes ?? 0)}</p>
    </article>
  `;
}

function renderSourceLinks() {
  if (!state.payload) {
    sourceLinks.innerHTML = '';
    return;
  }

  const src = state.payload.source || {};
  const links = [];

  if (src.monthly_page_url) {
    links.push(`<a href="${escapeHtml(src.monthly_page_url)}" target="_blank" rel="noreferrer">Página mensal da Receita</a>`);
  }
  if (src.xlsx_url) {
    links.push(`<a href="${escapeHtml(src.xlsx_url)}" target="_blank" rel="noreferrer">Planilha oficial (.xlsx)</a>`);
  }

  sourceLinks.innerHTML = links.join('');
}

function getRows() {
  if (!state.payload) {
    return [];
  }

  const rows = state.payload[state.view] || [];
  const query = normalizeText(state.query);
  if (!query) {
    return rows;
  }

  return rows.filter((item) => normalizeText(JSON.stringify(item)).includes(query));
}

function renderTable() {
  const rows = getRows();

  if (state.view === 'tributos') {
    tableHead.innerHTML = `
      <tr>
        <th>Vencimento</th>
        <th>Código</th>
        <th>Grupo</th>
        <th>Descrição</th>
        <th>Período de Apuração</th>
        <th>Periodicidade</th>
        <th>Documento</th>
      </tr>
    `;

    tableBody.innerHTML = rows
      .map(
        (item) => `
          <tr>
            <td>${formatDueDay(item)}</td>
            <td>${escapeHtml(item.code ?? '-')}</td>
            <td>${escapeHtml(item.group || '-')}</td>
            <td>${escapeHtml(item.description || '-')}</td>
            <td>${escapeHtml(item.apuration_period || '-')}</td>
            <td>${escapeHtml(item.periodicity || '-')}</td>
            <td>${escapeHtml(item.payment_document || '-')}</td>
          </tr>
        `,
      )
      .join('');
  } else {
    tableHead.innerHTML = `
      <tr>
        <th>Prazo</th>
        <th>Interessado</th>
        <th>Declaração / Documento</th>
        <th>Período de Referência</th>
        <th>Base Normativa</th>
      </tr>
    `;

    tableBody.innerHTML = rows
      .map(
        (item) => `
          <tr>
            <td>${escapeHtml(item.due_day ?? '-')}</td>
            <td>${escapeHtml(item.interested || '-')}</td>
            <td>${escapeHtml(item.description || '-')}</td>
            <td>${escapeHtml(item.reference_period || '-')}</td>
            <td>${escapeHtml(item.legal_basis || '-')}</td>
          </tr>
        `,
      )
      .join('');
  }

  if (rows.length === 0) {
    const tpl = document.getElementById('empty-state-template');
    tableBody.innerHTML = tpl.innerHTML;
  }
}

function inferAgendaPeriod() {
  if (!state.payload) {
    return null;
  }

  const srcUrl = state.payload.source?.monthly_page_url || '';
  const urlMatch = srcUrl.match(/\/(20\d{2})\/([A-Za-zÀ-ÿ-]+)\/?$/);
  if (urlMatch) {
    const year = Number(urlMatch[1]);
    const slug = normalizeText(urlMatch[2]).replaceAll('-', ' ');
    const monthToken = slug.split(' ')[0];
    const month = PT_MONTH_TO_NUM[monthToken];
    if (year && month) {
      return { year, month, label: `${PT_MONTH_LABEL[month]}/${year}` };
    }
  }

  const comp = state.payload.competence || {};
  if (comp.year && comp.month) {
    return {
      year: Number(comp.year),
      month: Number(comp.month),
      label: comp.label || `${PT_MONTH_LABEL[Number(comp.month)]}/${comp.year}`,
    };
  }

  return null;
}

function splitRowsByDay(rows) {
  const dayMap = new Map();
  const dailyRows = [];

  rows.forEach((item) => {
    const dueDay = Number(item.due_day);

    if (state.view === 'tributos' && item.due_type === 'daily') {
      dailyRows.push(item);
      return;
    }

    if (Number.isInteger(dueDay) && dueDay > 0 && dueDay <= 31) {
      if (!dayMap.has(dueDay)) {
        dayMap.set(dueDay, []);
      }
      dayMap.get(dueDay).push(item);
    }
  });

  return { dayMap, dailyRows };
}

function calendarPreview(item) {
  if (state.view === 'tributos') {
    const code = item.code ? ` (${item.code})` : '';
    return truncate(`${item.group || 'Tributo'}${code}`);
  }
  return truncate(item.description || 'Declaração');
}

function ensureSelectedDay(dayMap) {
  const days = [...dayMap.keys()].sort((a, b) => a - b);
  if (!days.length) {
    state.selectedDay = null;
    return;
  }

  if (!state.selectedDay || !dayMap.has(state.selectedDay)) {
    state.selectedDay = days[0];
  }
}

function buildCalendarGrid(period, dayMap) {
  const daysInMonth = new Date(period.year, period.month, 0).getDate();
  const firstWeekday = (new Date(period.year, period.month - 1, 1).getDay() + 6) % 7;

  const weekdaysHtml = WEEKDAYS.map((day) => `<div class="calendar-weekday">${day}</div>`).join('');

  let cells = '';
  for (let i = 0; i < firstWeekday; i += 1) {
    cells += '<div class="calendar-cell calendar-cell--empty"></div>';
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    const items = dayMap.get(day) || [];
    const selectedClass = state.selectedDay === day ? 'is-selected' : '';
    const preview = items
      .slice(0, 3)
      .map((item) => `<p class="calendar-day__item">${escapeHtml(calendarPreview(item))}</p>`)
      .join('');

    cells += `
      <div class="calendar-cell">
        <button class="calendar-day ${selectedClass}" data-day="${day}">
          <div class="calendar-day__top">
            <span class="calendar-day__number">${day}</span>
            ${items.length ? `<span class="calendar-day__count">${items.length}</span>` : ''}
          </div>
          <div class="calendar-day__items">${preview}</div>
        </button>
      </div>
    `;
  }

  return `
    <div class="calendar-weekdays">${weekdaysHtml}</div>
    <div class="calendar-cells">${cells}</div>
  `;
}

function renderCalendarDaily(dailyRows) {
  if (!dailyRows.length) {
    calendarDaily.innerHTML = '';
    return;
  }

  const items = dailyRows
    .slice(0, 8)
    .map((item) => {
      const text = state.view === 'tributos' ? `${item.group} - ${item.description}` : item.description;
      return `<li class="calendar-daily__item">${escapeHtml(truncate(text, 130))}</li>`;
    })
    .join('');

  const extra = dailyRows.length > 8 ? `<li class="calendar-daily__item">+ ${dailyRows.length - 8} itens</li>` : '';

  calendarDaily.innerHTML = `
    <h3 class="calendar-daily__title">Vencimentos diários</h3>
    <ul class="calendar-daily__list">
      ${items}
      ${extra}
    </ul>
  `;
}

function detailTitle(item) {
  if (state.view === 'tributos') {
    const code = item.code ? ` (${item.code})` : '';
    return `${item.group || 'Tributo'}${code}`;
  }
  return item.description || 'Declaração';
}

function detailMeta(item) {
  if (state.view === 'tributos') {
    return [item.description, item.apuration_period, item.payment_document].filter(Boolean).join(' · ');
  }
  return [item.interested, item.reference_period, item.legal_basis].filter(Boolean).join(' · ');
}

function renderCalendarDetails(dayMap) {
  if (!state.selectedDay || !dayMap.has(state.selectedDay)) {
    calendarDetails.innerHTML = '<p class="empty-state">Nenhum evento com os filtros atuais.</p>';
    return;
  }

  const rows = dayMap.get(state.selectedDay) || [];
  const items = rows
    .map(
      (item) => `
        <li class="calendar-details__item">
          <p class="calendar-details__item-title">${escapeHtml(detailTitle(item))}</p>
          <p class="calendar-details__item-meta">${escapeHtml(detailMeta(item) || '-')}</p>
        </li>
      `,
    )
    .join('');

  calendarDetails.innerHTML = `
    <h3 class="calendar-details__title">Dia ${state.selectedDay}</h3>
    <ul class="calendar-details__list">${items}</ul>
  `;
}

function bindCalendarDayEvents(dayMap) {
  document.querySelectorAll('.calendar-day[data-day]').forEach((button) => {
    button.addEventListener('click', () => {
      state.selectedDay = Number(button.dataset.day);
      renderCalendarDetails(dayMap);
      document.querySelectorAll('.calendar-day').forEach((btn) => {
        btn.classList.toggle('is-selected', Number(btn.dataset.day) === state.selectedDay);
      });
    });
  });
}

function renderCalendar() {
  if (!state.payload) {
    calendarHeader.innerHTML = '';
    calendarGrid.innerHTML = '';
    calendarDaily.innerHTML = '';
    calendarDetails.innerHTML = '';
    return;
  }

  const rows = getRows();
  const { dayMap, dailyRows } = splitRowsByDay(rows);
  const period = inferAgendaPeriod();

  calendarHeader.innerHTML = `
    <div>
      <h2 class="calendar-header__title">${escapeHtml(getCurrentTypeLabel())} em calendário</h2>
      <p class="calendar-header__hint">${escapeHtml(period?.label || 'Mês não identificado')}</p>
    </div>
    <p class="calendar-header__hint">${escapeHtml(rows.length)} itens após filtros</p>
  `;

  if (!period) {
    calendarGrid.innerHTML = '<p class="empty-state">Não foi possível identificar o mês para montar o calendário.</p>';
    calendarDaily.innerHTML = '';
    calendarDetails.innerHTML = '';
    return;
  }

  ensureSelectedDay(dayMap);
  calendarGrid.innerHTML = buildCalendarGrid(period, dayMap);
  renderCalendarDaily(dailyRows);
  renderCalendarDetails(dayMap);
  bindCalendarDayEvents(dayMap);
}

function setView(view) {
  state.view = view;
  state.selectedDay = null;
  document.querySelectorAll('.segmented__button[data-view]').forEach((btn) => {
    btn.classList.toggle('is-active', btn.dataset.view === view);
  });
  renderTable();
  renderCalendar();
}

function setDisplayMode(mode) {
  state.displayMode = mode;
  document.querySelectorAll('.segmented__button[data-mode]').forEach((btn) => {
    btn.classList.toggle('is-active', btn.dataset.mode === mode);
  });

  tablePanel.classList.toggle('is-hidden', mode === 'calendar');
  calendarPanel.classList.toggle('is-hidden', mode !== 'calendar');

  if (mode === 'calendar') {
    renderCalendar();
  }
}

async function loadMonth(index) {
  state.monthIndex = index;
  state.selectedDay = null;

  const month = state.months[index];
  if (!month) {
    state.payload = null;
    renderSummary();
    renderSourceLinks();
    renderTable();
    renderCalendar();
    return;
  }

  const cacheKey = encodeURIComponent(month.payload_generated_at || Date.now().toString());
  const res = await fetch(`/data/${month.file}?v=${cacheKey}`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Falha ao carregar ${month.file}`);
  }

  state.payload = await res.json();
  renderSummary();
  renderSourceLinks();
  renderTable();
  renderCalendar();
}

function bindEvents() {
  document.getElementById('tab-tributos').addEventListener('click', () => setView('tributos'));
  document.getElementById('tab-declaracoes').addEventListener('click', () => setView('declaracoes'));

  document.getElementById('mode-list').addEventListener('click', () => setDisplayMode('list'));
  document.getElementById('mode-calendar').addEventListener('click', () => setDisplayMode('calendar'));

  monthSelect.addEventListener('change', async (event) => {
    await loadMonth(Number(event.target.value));
  });

  searchInput.addEventListener('input', (event) => {
    state.query = event.target.value;
    state.selectedDay = null;
    renderTable();
    renderCalendar();
  });
}

function renderMonthOptions() {
  monthSelect.innerHTML = state.months
    .map((month, index) => `<option value="${index}">${escapeHtml(month.label || month.file)}</option>`)
    .join('');
}

async function bootstrap() {
  bindEvents();

  const res = await fetch(`/data/index.json?v=${Date.now()}`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error('Falha ao carregar data/index.json');
  }

  const indexData = await res.json();
  state.months = indexData.months || [];

  if (state.months.length === 0) {
    tableBody.innerHTML = '<tr><td class="empty-state">Nenhum mês disponível no diretório data/.</td></tr>';
    return;
  }

  renderMonthOptions();
  await loadMonth(0);
}

bootstrap().catch((err) => {
  console.error(err);
  tableBody.innerHTML = `<tr><td class="empty-state">Erro ao carregar dados: ${escapeHtml(err.message)}</td></tr>`;
});
