const state = {
  leyId: null,
  articuloId: null,
  textoVigente: "",
  impactoActual: null,
  categoriaActual: "",
  coleccionActual: "",
  areaActual: "",
  articulosData: [],
};

function escHtml(texto) {
  return (texto || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function apiFetch(url, opts = {}) {
  return fetch(url, { credentials: "same-origin", ...opts });
}

/* ─── Historial de navegación ─── */
const historial = { pila: [], pos: -1, navegando: false };

function histPush(entry) {
  if (historial.navegando) return;
  historial.pila.splice(historial.pos + 1);
  historial.pila.push(entry);
  historial.pos = historial.pila.length - 1;
  histActualizar();
}

function histActualizar() {
  const btn_a = $("#btn-atras");
  const btn_d = $("#btn-adelante");
  if (btn_a) btn_a.disabled = historial.pos <= 0;
  if (btn_d) btn_d.disabled = historial.pos >= historial.pila.length - 1;
}

function histIr(dir) {
  const np = historial.pos + dir;
  if (np < 0 || np >= historial.pila.length) return;
  historial.pos = np;
  historial.navegando = true;
  const e = historial.pila[np];
  if (e.tipo === "inicio") irInicio();
  else if (e.tipo === "categoria") abrirCategoria(e.rango);
  else if (e.tipo === "coleccion") abrirColeccion(e.colId);
  else if (e.tipo === "area") abrirArea(e.areaId);
  else if (e.tipo === "ley") cargarLey(e.leyId);
  historial.navegando = false;
  histActualizar();
}

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const infoCategorias = {};
const infoColecciones = {};
const infoAreas = {};

const ICONOS_CAT = {
  "Constitución": "📜",
  "Ley Orgánica": "⚖️",
  "Ley": "📄",
  "Ley Foral": "🏛️",
  "Real Decreto Legislativo": "📋",
  "Real Decreto-ley": "⚡",
};

let authBloqueo = false;

function perfil() {
  return {
    situacion: $("#perfil-situacion").value,
    ingresos_anuales: Number($("#perfil-ingresos").value || 28000),
    tamano_hogar: Number($("#perfil-hogar").value || 2),
    region: "España",
  };
}

/* ─── Navegación por paneles ─── */
const PANELES = ["explorar", "articulo", "impacto", "comunidad"];
const PANEL_ETIQUETAS = {
  explorar: "Explorar",
  articulo: "Artículo",
  impacto: "Impacto",
  comunidad: "Comunidad",
};

function esMovil() {
  return window.matchMedia("(max-width: 1100px)").matches;
}

function panelActual() {
  const activo = document.querySelector(".nav-btn.active");
  return activo?.dataset.panel || "explorar";
}

function actualizarNavSecciones(nombre) {
  $$(".nav-btn").forEach((el) => {
    el.classList.toggle("active", el.dataset.panel === nombre);
  });
  const label = $("#nav-flotante-label");
  if (label) label.textContent = PANEL_ETIQUETAS[nombre] || nombre;
  const idx = PANELES.indexOf(nombre);
  const arriba = idx <= 0;
  const abajo = idx < 0 || idx >= PANELES.length - 1;
  ["btn-seccion-arriba", "btn-flotante-arriba"].forEach((id) => {
    const btn = $("#" + id);
    if (btn) btn.disabled = authBloqueo || arriba;
  });
  ["btn-seccion-abajo", "btn-flotante-abajo"].forEach((id) => {
    const btn = $("#" + id);
    if (btn) btn.disabled = authBloqueo || abajo;
  });
}

function mostrarPanel(nombre) {
  if (authBloqueo && nombre !== "comunidad") return;
  if (!PANELES.includes(nombre)) return;

  if (esMovil()) {
    $$(".panel").forEach((el) => {
      el.classList.toggle("visible", el.dataset.panel === nombre);
    });
  } else {
    const panel = document.querySelector(`.panel[data-panel="${nombre}"]`);
    if (panel) {
      panel.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
      panel.classList.add("panel-foco");
      setTimeout(() => panel.classList.remove("panel-foco"), 900);
    }
  }
  actualizarNavSecciones(nombre);
  const navFlot = document.querySelector(".nav-flotante");
  if (navFlot) {
    // En Comunidad el bloque flotante derecho tapaba los filtros del foro
    navFlot.hidden = nombre === "comunidad";
  }
}

function moverSeccion(delta) {
  if (authBloqueo) return;
  const idx = PANELES.indexOf(panelActual());
  const actual = idx < 0 ? 0 : idx;
  const nuevo = Math.max(0, Math.min(PANELES.length - 1, actual + delta));
  if (nuevo !== actual) mostrarPanel(PANELES[nuevo]);
}

function setAuthBloqueo(valor) {
  authBloqueo = !!valor;
  $$(".nav-btn").forEach((btn) => {
    btn.disabled = authBloqueo && btn.dataset.panel !== "comunidad";
  });
  if (authBloqueo) mostrarPanel("comunidad");
  else actualizarNavSecciones(panelActual());
}

async function limpiarSesion() {
  try {
    await apiFetch("/api/logout", { method: "POST" });
  } catch {}
  localStorage.removeItem("rg_uid");
  localStorage.removeItem("rg_username");
  localStorage.removeItem("rg_nombre_visible");
  setAuthBloqueo(true);
  $("#modal-auth").hidden = false;
  const tab = document.querySelector('#auth-box .auth-tab[data-auth="login"]');
  if (tab) mostrarAuthTab("login");
  actualizarSesionUI();
  $("#vista-perfil").hidden = true;
  $("#vista-comunidad-principal").hidden = false;
  $("#btn-mi-perfil").hidden = true;
  cargarCaptcha("login");
}

function aplicarSesion(data) {
  if (!data || !data.id) return;
  guardarUid(data.id);
  guardarUsername(data.username || "");
  guardarNombreVisible(data.nombre || "");
  pintarComunidad(data);
  mostrarBtnGuardar();
  actualizarSesionUI();
  setAuthBloqueo(false);
  $("#modal-auth").hidden = true;
  $("#btn-mi-perfil").hidden = false;
}

const captchaTokens = {};

async function cargarCaptcha(nombre) {
  const row = document.querySelector(`.captcha-row[data-captcha-for="${nombre}"]`);
  if (!row) return;
  try {
    const data = await (await fetch("/api/captcha", { credentials: "same-origin" })).json();
    captchaTokens[nombre] = data.token || "";
    const pregunta = row.querySelector(".captcha-pregunta");
    const input = row.querySelector(".captcha-respuesta");
    if (pregunta) pregunta.textContent = data.pregunta || "";
    if (input) input.value = "";
  } catch {
    captchaTokens[nombre] = "";
  }
}

function captchaPayload(nombre) {
  const row = document.querySelector(`.captcha-row[data-captcha-for="${nombre}"]`);
  const respuesta = row?.querySelector(".captcha-respuesta")?.value || "";
  return {
    captcha_token: captchaTokens[nombre] || "",
    captcha_respuesta: respuesta,
  };
}

document.querySelectorAll(".captcha-reload").forEach((btn) => {
  btn.addEventListener("click", () => {
    const row = btn.closest(".captcha-row");
    const nombre = row?.dataset.captchaFor;
    if (nombre) cargarCaptcha(nombre);
  });
});

$$(".nav-btn").forEach((el) => {
  el.addEventListener("click", () => mostrarPanel(el.dataset.panel));
});

["btn-seccion-arriba", "btn-flotante-arriba"].forEach((id) => {
  const btn = $("#" + id);
  if (btn) btn.addEventListener("click", () => moverSeccion(-1));
});
["btn-seccion-abajo", "btn-flotante-abajo"].forEach((id) => {
  const btn = $("#" + id);
  if (btn) btn.addEventListener("click", () => moverSeccion(1));
});

actualizarNavSecciones("explorar");

$("#btn-atras").addEventListener("click", () => histIr(-1));
$("#btn-adelante").addEventListener("click", () => histIr(1));

/* ─── Breadcrumb ─── */
function setBreadcrumb(niveles) {
  const bc = $("#breadcrumb");
  bc.innerHTML = "";
  niveles.forEach((n, i) => {
    if (i > 0) {
      const sep = document.createElement("span");
      sep.className = "bc-sep";
      bc.appendChild(sep);
    }
    const span = document.createElement("span");
    span.className = "bc-item" + (i === niveles.length - 1 ? " active" : "");
    span.textContent = n.label;
    span.dataset.nivel = n.nivel;
    span.addEventListener("click", () => n.action());
    bc.appendChild(span);
  });
}

/* ─── Vistas del explorador ─── */
function mostrarVista(nombre) {
  $("#vista-inicio").hidden = nombre !== "inicio";
  $("#vista-area").hidden = nombre !== "area";
  $("#vista-categoria").hidden = nombre !== "categoria";
  $("#vista-articulos").hidden = nombre !== "articulos";
}

function irInicio() {
  mostrarVista("inicio");
  setBreadcrumb([{ label: "Inicio", nivel: "inicio", action: irInicio }]);
  $("#buscar").value = "";
  $("#lista-leyes").innerHTML = "";
  state.areaActual = "";
  state.categoriaActual = "";
  state.coleccionActual = "";
  histPush({ tipo: "inicio" });
}

/* ─── Áreas de materia ─── */
async function cargarAreas() {
  try {
    const data = await (await fetch("/api/areas")).json();
    data.forEach((area) => {
      infoAreas[area.id] = area;
    });
    const grid = $("#areas-grid");
    if (!grid) return;
    grid.innerHTML = data
      .map(
        (area) => `
      <button type="button" class="cat-card area-card" data-area="${escHtml(area.id)}">
        <div class="cat-icono">${area.icono || "📑"}</div>
        <div class="cat-info">
          <div class="cat-nombre">${escHtml(area.nombre)}</div>
          <div class="cat-total">${area.total === 1 ? "1 norma" : `${area.total} normas`}${
          area.ejemplos ? ` · ${area.ejemplos} ejemplo${area.ejemplos === 1 ? "" : "s"}` : ""
        }</div>
        </div>
      </button>`
      )
      .join("");
    grid.querySelectorAll(".area-card").forEach((el) => {
      el.addEventListener("click", () => abrirArea(el.dataset.area));
    });
  } catch {
    const grid = $("#areas-grid");
    if (grid) grid.innerHTML = '<div class="empty">No se pudieron cargar las áreas.</div>';
  }
}

async function abrirArea(areaId) {
  if (!areaId) return;
  state.areaActual = areaId;
  state.categoriaActual = "";
  state.coleccionActual = "";
  mostrarVista("area");
  histPush({ tipo: "area", areaId });
  $("#buscar-area").value = "";
  $("#lista-leyes-area").innerHTML = '<div class="empty">Cargando…</div>';
  $("#area-ejemplos").innerHTML = "";

  const res = await fetch(`/api/area/${encodeURIComponent(areaId)}?limit=200`);
  const data = await res.json();
  if (!res.ok) {
    $("#lista-leyes-area").innerHTML = `<div class="empty">${escHtml(data.error || "Área no encontrada")}</div>`;
    return;
  }

  setBreadcrumb([
    { label: "Inicio", nivel: "inicio", action: irInicio },
    { label: data.nombre, nivel: "area", action: () => abrirArea(areaId) },
  ]);
  $("#area-descripcion").textContent = data.descripcion || "";
  $("#area-contador").textContent =
    data.total === 1 ? "1 norma relacionada" : `${data.total} normas relacionadas`;

  const ejemplos = data.ejemplos || [];
  const contEj = $("#area-ejemplos");
  if (!ejemplos.length) {
    contEj.innerHTML = '<div class="empty">Sin ejemplos guiados en esta área.</div>';
  } else {
    contEj.innerHTML = ejemplos
      .map(
        (ej, idx) => `
      <button type="button" class="ejemplo-card" data-idx="${idx}">
        <span class="ejemplo-etiqueta">Ejemplo guiado</span>
        <span class="ejemplo-titulo">${escHtml(ej.titulo || "Abrir artículo")}</span>
        <span class="ejemplo-accion">Abrir y simular →</span>
      </button>`
      )
      .join("");
    contEj.querySelectorAll(".ejemplo-card").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const ej = ejemplos[Number(btn.dataset.idx)];
        if (!ej?.ley_id) return;
        await cargarLey(ej.ley_id);
        if (ej.articulo_id) {
          await cargarArticulo(ej.articulo_id);
          mostrarPanel("articulo");
          activarTab("reforma");
        }
      });
    });
  }

  renderListaLeyes(data.items || [], "#lista-leyes-area");
}

async function filtrarArea() {
  const areaId = state.areaActual;
  if (!areaId) return;
  const q = $("#buscar-area").value.trim();
  const res = await fetch(`/api/area/${encodeURIComponent(areaId)}?${new URLSearchParams({ q, limit: "200" })}`);
  const data = await res.json();
  if (!res.ok) return;
  $("#area-contador").textContent =
    data.total === 1 ? "1 norma relacionada" : `${data.total} normas relacionadas`;
  renderListaLeyes(data.items || [], "#lista-leyes-area");
}

/* ─── Categorías ─── */
async function cargarCategorias() {
  try {
    const data = await (await fetch("/api/categorias")).json();
    data.forEach((cat) => { if (cat.info) infoCategorias[cat.rango] = cat.info; });
    const grid = $("#categorias-grid");
    grid.innerHTML = data
      .map(
        (cat) => `
      <div class="cat-card${cat.rango === "Constitución" ? " constitucion" : ""}" data-rango="${cat.rango}">
        <div class="cat-icono">${ICONOS_CAT[cat.rango] || "📑"}</div>
        <div class="cat-info">
          <div class="cat-nombre">${cat.rango}</div>
          <div class="cat-total">${cat.total === 1 ? "1 norma" : cat.total + " normas"}</div>
        </div>
      </div>`
      )
      .join("");
    grid.querySelectorAll(".cat-card").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const rango = el.dataset.rango;
        if (rango.normalize("NFC").startsWith("Constituci")) {
          cargarLey("BOE-A-1978-31229");
          return;
        }
        abrirCategoria(rango);
      });
    });
  } catch {
    $("#categorias-grid").innerHTML = '<div class="empty">No se pudieron cargar las categorías.</div>';
  }
}

/* ─── Colecciones temáticas ─── */
async function cargarColecciones() {
  try {
    const data = await (await fetch("/api/colecciones")).json();
    data.forEach((col) => { if (col.info) infoColecciones[col.id] = col.info; });
    const grid = $("#colecciones-grid");
    grid.innerHTML = data
      .map(
        (col) => `
      <div class="cat-card tematica" data-col="${col.id}">
        <div class="cat-icono">${col.icono}</div>
        <div class="cat-info">
          <div class="cat-nombre">${col.nombre}</div>
          <div class="cat-total">${col.total === 1 ? "1 norma" : col.total + " normas"}</div>
        </div>
      </div>`
      )
      .join("");
    grid.querySelectorAll(".cat-card").forEach((el) => {
      el.addEventListener("click", () => abrirColeccion(el.dataset.col));
    });
  } catch {
    $("#colecciones-grid").innerHTML = '<div class="empty">No se pudieron cargar las colecciones.</div>';
  }
}

async function abrirColeccion(colId) {
  state.categoriaActual = "";
  state.coleccionActual = colId;
  mostrarVista("categoria");
  histPush({ tipo: "coleccion", colId });
  const nombre = colId.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  setBreadcrumb([
    { label: "Inicio", nivel: "inicio", action: irInicio },
    { label: nombre, nivel: "categoria", action: () => abrirColeccion(colId) },
  ]);
  $("#buscar-cat").value = "";
  $("#lista-leyes-cat").innerHTML = '<div class="empty">Cargando…</div>';
  renderInfoCategoria(infoColecciones[colId] || null);

  const res = await fetch(`/api/coleccion/${encodeURIComponent(colId)}?limit=200`);
  const data = await res.json();
  $("#categoria-contador").textContent = `${data.total} normas`;
  renderListaLeyes(data.items, "#lista-leyes-cat");
}

/* ─── Panel informativo ─── */
function renderInfoCategoria(info) {
  const panel = $("#info-categoria");
  if (!info) { panel.hidden = true; return; }
  panel.hidden = false;
  panel.innerHTML = `
    <button type="button" class="info-toggle" onclick="this.parentElement.classList.toggle('expandida')">
      ℹ️ Información sobre esta categoría <span class="info-flecha">▼</span>
    </button>
    <div class="info-cuerpo">
      <div class="info-seccion">
        <h5>📋 Cómo se generó</h5>
        <p>${info.como}</p>
      </div>
      <div class="info-seccion">
        <h5>👥 Quién la generó</h5>
        <p>${info.quien}</p>
      </div>
      <div class="info-seccion">
        <h5>❓ Por qué se generó</h5>
        <p>${info.porque}</p>
      </div>
    </div>`;
}

/* ─── Abrir una categoría ─── */
async function abrirCategoria(rango) {
  state.categoriaActual = rango;
  state.coleccionActual = "";
  mostrarVista("categoria");
  histPush({ tipo: "categoria", rango });
  setBreadcrumb([
    { label: "Inicio", nivel: "inicio", action: irInicio },
    { label: rango, nivel: "categoria", action: () => abrirCategoria(rango) },
  ]);
  $("#buscar-cat").value = "";
  $("#lista-leyes-cat").innerHTML = '<div class="empty">Cargando…</div>';
  renderInfoCategoria(infoCategorias[rango] || null);

  const res = await fetch(`/api/catalogo?${new URLSearchParams({ rango, limit: "200" })}`);
  const data = await res.json();
  $("#categoria-contador").textContent = `${data.total} normas`;
  renderListaLeyes(data.items, "#lista-leyes-cat");
}

/* ─── Buscador global ─── */
async function buscarLeyes() {
  const q = $("#buscar").value.trim();
  const lista = $("#lista-leyes");
  if (!q) {
    lista.innerHTML = "";
    return;
  }
  const res = await fetch(`/api/catalogo?${new URLSearchParams({ q, limit: "60" })}`);
  const data = await res.json();
  if (!data.items.length) {
    lista.innerHTML = '<div class="empty">No se encontraron normas.</div>';
    return;
  }
  renderListaLeyes(data.items, "#lista-leyes");
}

/* ─── Filtro dentro de categoría ─── */
async function filtrarCategoria() {
  const q = $("#buscar-cat").value.trim();
  let res;
  if (state.coleccionActual) {
    res = await fetch(`/api/coleccion/${encodeURIComponent(state.coleccionActual)}?${new URLSearchParams({ q, limit: "200" })}`);
  } else {
    const rango = state.categoriaActual;
    res = await fetch(`/api/catalogo?${new URLSearchParams({ q, rango, limit: "200" })}`);
  }
  const data = await res.json();
  renderListaLeyes(data.items, "#lista-leyes-cat");
}

/* ─── Renderizar lista de leyes ─── */
function renderListaLeyes(items, selector) {
  const lista = $(selector);
  lista.innerHTML = items
    .map(
      (item) => `
    <div class="ley-item" data-id="${item.identificador}">
      <div class="titulo-ley">${escHtml(item.titulo || item.identificador)}</div>
      <div class="meta">${escHtml(item.rango || "")}</div>
    </div>`
    )
    .join("");
  lista.querySelectorAll(".ley-item").forEach((el) => {
    el.addEventListener("click", () => cargarLey(el.dataset.id));
  });
}

/* ─── Cargar una ley (mostrar artículos) ─── */

function guardarNavegacion() {
  if (!state.leyId) return;
  try {
    sessionStorage.setItem(
      "rg_nav",
      JSON.stringify({ leyId: state.leyId, articuloId: state.articuloId || "" })
    );
  } catch {}
}

async function restaurarNavegacionGuardada() {
  let raw = null;
  try {
    raw = sessionStorage.getItem("rg_nav");
  } catch {
    return;
  }
  if (!raw) return;
  try {
    const nav = JSON.parse(raw);
    if (!nav?.leyId) return;
    await cargarLey(nav.leyId);
    if (nav.articuloId) {
      await cargarArticulo(nav.articuloId);
      mostrarPanel("articulo");
    }
  } catch {}
}

async function cargarLey(id) {
  state.leyId = id;
  state.articuloId = null;
  histPush({ tipo: "ley", leyId: id });
  const res = await fetch(`/api/ley/${encodeURIComponent(id)}`);
  const data = await res.json();

  const tituloCorto = (data.titulo || id).substring(0, 80);

  mostrarVista("articulos");

  const bcLevels = [{ label: "Inicio", nivel: "inicio", action: irInicio }];
  if (state.areaActual) {
    const areaId = state.areaActual;
    const areaNombre = infoAreas[areaId]?.nombre || areaId;
    bcLevels.push({ label: areaNombre, nivel: "area", action: () => abrirArea(areaId) });
  }
  if (state.categoriaActual) {
    const r = state.categoriaActual;
    bcLevels.push({ label: r, nivel: "categoria", action: () => abrirCategoria(r) });
  }
  bcLevels.push({ label: tituloCorto, nivel: "articulos", action: () => cargarLey(id) });
  setBreadcrumb(bcLevels);

  $("#titulo-ley-sel").textContent = data.titulo || id;
  state.articulosData = data.articulos || [];

  renderArticulosLey("");

  $("#titulo-articulo").textContent = data.titulo || "Selecciona un artículo";
  $("#meta-articulo").textContent = "";
  $("#texto-articulo").textContent = "";
  $("#seccion-comentarios-art").hidden = true;
  const enlaceOpLey = $("#enlace-opiniones-wrap");
  if (enlaceOpLey) enlaceOpLey.hidden = true;
  $("#seccion-comentarios-ley").hidden = false;
  cargarComentarios("ley", id, "", data.titulo || id, "");
  guardarNavegacion();
}

function renderArticulosLey(filtro) {
  const contenedor = $("#lista-articulos-ley");
  const f = filtro.toLowerCase();
  const arts = f
    ? state.articulosData.filter(
        (a) =>
          a.titulo.toLowerCase().includes(f) ||
          a.numero.toLowerCase().includes(f) ||
          (a.seccion || "").toLowerCase().includes(f) ||
          (a.extracto || "").toLowerCase().includes(f)
      )
    : state.articulosData;

  if (!arts.length) {
    contenedor.innerHTML = f
      ? '<div class="empty">Ningún artículo coincide.</div>'
      : '<div class="empty">Esta norma no tiene artículos parseables.</div>';
    return;
  }

  contenedor.innerHTML = arts
    .map(
      (a) => `
    <div class="art-item" data-id="${a.id}">
      <div class="art-num">${a.numero}</div>
      <div class="art-info">
        <div class="art-titulo">${escHtml(a.titulo)}</div>
        <div class="art-extracto">${escHtml(a.extracto || "")}</div>
        <div class="meta">${escHtml(a.seccion || "")}</div>
      </div>
    </div>`
    )
    .join("");

  contenedor.querySelectorAll(".art-item").forEach((el) => {
    el.addEventListener("click", () => {
      cargarArticulo(el.dataset.id);
      mostrarPanel("articulo");
    });
  });
}

/* ─── Cargar un artículo ─── */
async function cargarArticulo(articuloId) {
  if (!state.leyId) return;
  state.articuloId = articuloId;
  $$(".art-item").forEach((el) => el.classList.toggle("active", el.dataset.id === articuloId));
  const params = new URLSearchParams(perfil());
  const res = await fetch(
    `/api/ley/${encodeURIComponent(state.leyId)}/articulo/${encodeURIComponent(articuloId)}?${params}`
  );
  const data = await res.json();
  const art = data.articulo;
  state.textoVigente = art.texto;
  state.impactoActual = data.impacto;
  $("#titulo-articulo").textContent = `${art.titulo} — ${data.ley_titulo}`;
  $("#meta-articulo").textContent = art.seccion || "";
  $("#texto-articulo").textContent = art.texto;
  $("#texto-reforma").value = art.texto;
  const cont = $("#impacto-contenido");
  cont.classList.remove("empty");
  renderImpacto(data.impacto, cont);
  $("#impacto-reforma").hidden = true;
  $("#btn-guardar-sim").hidden = !uid();
  $("#btn-guardar-art").hidden = !uid();
  $("#seccion-comentarios-art").hidden = false;
  const enlaceOp = $("#enlace-opiniones-wrap");
  if (enlaceOp) enlaceOp.hidden = false;
  await cargarComentarios(
    "art",
    state.leyId,
    articuloId,
    data.ley_titulo || state.leyId,
    `${art.titulo} — ${data.ley_titulo || ""}`.trim()
  );
  const seccionOp = $("#seccion-comentarios-art");
  if (seccionOp && !seccionOp.hidden) {
    seccionOp.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  guardarNavegacion();
}

/* ─── Impacto ─── */
function barra(clase, etiqueta, valor, max = 100) {
  const pct = Math.max(0, Math.min(100, (valor / max) * 100));
  return `
    <div class="metric">
      <div class="metric-label"><span>${etiqueta}</span><strong>${valor.toFixed ? valor.toFixed(1) : valor}%</strong></div>
      <div class="bar ${clase}"><span style="width:${pct}%"></span></div>
    </div>`;
}

function beneficiarioLabel(ben) {
  if (!ben) return "";
  const map = {
    ciudadanos: { icon: "👥", text: "Beneficia a los ciudadanos", cls: "ben-ciudadanos" },
    gobierno:   { icon: "🏛️", text: "Beneficia al gobierno",     cls: "ben-gobierno" },
    ambos:      { icon: "🤝", text: "Beneficia a ambos",         cls: "ben-ambos" },
  };
  const b = map[ben.beneficiario] || map.ambos;
  return `
    <div class="beneficiario-box ${b.cls}">
      <div class="ben-header">${b.icon} <strong>${b.text}</strong></div>
      <div class="ben-barras">
        <div class="ben-barra">
          <span class="ben-label">Ciudadanos</span>
          <div class="ben-track"><div class="ben-fill ben-fill-ciud" style="width:${ben.ciudadanos_pct}%"></div></div>
          <span class="ben-pct">${ben.ciudadanos_pct}%</span>
        </div>
        <div class="ben-barra">
          <span class="ben-label">Gobierno</span>
          <div class="ben-track"><div class="ben-fill ben-fill-gob" style="width:${ben.gobierno_pct}%"></div></div>
          <span class="ben-pct">${ben.gobierno_pct}%</span>
        </div>
      </div>
    </div>`;
}

function signoLabel(signo) {
  const map = {
    positivo: { icon: "🟢", text: "Impacto positivo", cls: "signo-positivo" },
    negativo: { icon: "🔴", text: "Impacto negativo", cls: "signo-negativo" },
    mixto:    { icon: "🟡", text: "Impacto mixto",    cls: "signo-mixto" },
  };
  const s = map[signo] || map.mixto;
  return `<span class="signo-badge ${s.cls}">${s.icon} ${s.text}</span>`;
}

function renderImpacto(impacto, contenedor, titulo = "Situación actual") {
  const euros = impacto.impacto_presupuestario_millones_eur;
  const afectados = impacto.afectados_estimados;
  contenedor.innerHTML = `
    <h3 style="margin:0 0 .5rem;font-size:1rem;">${titulo}</h3>
    <div style="margin-bottom:.6rem">${signoLabel(impacto.signo)}</div>
    ${beneficiarioLabel(impacto.beneficiario)}
    ${barra("social", "Impacto social (nacional)", impacto.social_nacional)}
    ${barra("economico", "Impacto económico (nacional)", impacto.economico_nacional)}
    ${barra("social", "Impacto social (individual)", impacto.social_individual)}
    ${barra("economico", "Impacto económico (individual)", impacto.economico_individual)}
    ${barra("intensidad", "Intensidad global", impacto.intensidad)}
    <div class="metric-label"><span>Confianza del modelo</span><strong>${impacto.confianza}%</strong></div>
    ${euros != null ? `<div class="metric-label"><span>Impacto presupuestario</span><strong>~${euros.toLocaleString("es-ES")} M€/año</strong></div>` : ""}
    ${afectados != null ? `<div class="metric-label"><span>Personas afectadas</span><strong>${afectados.toLocaleString("es-ES")}</strong></div>` : ""}
    <div class="chips">${(impacto.etiquetas || []).map((t) => `<span class="chip">${t}</span>`).join("")}</div>
    <ul style="margin:.5rem 0 0;padding-left:1.1rem;color:var(--muted);font-size:.85rem;">
      ${(impacto.explicacion || []).map((e) => `<li>${e}</li>`).join("")}
    </ul>`;
}

function renderDelta(delta, resumen, aviso, signoReforma, benDespues) {
  const fmt = (v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}`;
  const cls = (v) => (v > 0 ? "positive" : v < 0 ? "negative" : "");
  return `
    <h3 style="margin:1rem 0 .5rem;font-size:1rem;">Resultado de la reforma</h3>
    <div style="margin-bottom:.6rem">${signoLabel(signoReforma || "mixto")}</div>
    ${beneficiarioLabel(benDespues)}
    <div class="metric-label delta ${cls(delta.social_nacional)}"><span>Δ Social nacional</span><strong>${fmt(delta.social_nacional)}</strong></div>
    <div class="metric-label delta ${cls(delta.economico_nacional)}"><span>Δ Económico nacional</span><strong>${fmt(delta.economico_nacional)}</strong></div>
    <div class="metric-label delta ${cls(delta.social_individual)}"><span>Δ Social individual</span><strong>${fmt(delta.social_individual)}</strong></div>
    <div class="metric-label delta ${cls(delta.economico_individual)}"><span>Δ Económico individual</span><strong>${fmt(delta.economico_individual)}</strong></div>
    <div class="metric-label delta ${cls(delta.intensidad)}"><span>Δ Intensidad global</span><strong>${fmt(delta.intensidad)}</strong></div>
    ${delta.presupuesto_millones_eur != null ? `<div class="metric-label delta ${cls(delta.presupuesto_millones_eur)}"><span>Δ Presupuesto</span><strong>${fmt(delta.presupuesto_millones_eur)} M€/año</strong></div>` : ""}
    ${delta.personas_afectadas != null ? `<div class="metric-label delta ${cls(delta.personas_afectadas)}"><span>Δ Personas afectadas</span><strong>${delta.personas_afectadas > 0 ? "+" : ""}${Number(delta.personas_afectadas).toLocaleString("es-ES")}</strong></div>` : ""}
    <ul style="margin:.75rem 0 0;padding-left:1.1rem;font-size:.85rem;color:var(--text);">
      ${(resumen || []).map((r) => `<li>${r}</li>`).join("")}
    </ul>
    <p class="aviso" style="margin-top:.75rem;">${aviso || ""}</p>`;
}

async function simularReforma() {
  if (!state.leyId || !state.articuloId) return;
  const res = await fetch("/api/simular", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ley_id: state.leyId,
      articulo_id: state.articuloId,
      texto_propuesto: $("#texto-reforma").value,
      perfil: perfil(),
    }),
  });
  const data = await res.json();
  const box = $("#impacto-reforma");
  box.hidden = false;
  box.innerHTML = renderDelta(data.delta, data.resumen, data.aviso, data.signo_reforma, data.beneficiario_despues);
  renderImpacto(data.despues, $("#impacto-contenido"), "Después de la reforma");
}

function activarTab(tab) {
  $$(".tab").forEach((el) => el.classList.toggle("active", el.dataset.tab === tab));
  $("#vista-actual").hidden = tab !== "actual";
  $("#vista-reforma").hidden = tab !== "reforma";
}

/* ─── Búsqueda avanzada ─── */
$("#btn-avanzada").addEventListener("click", () => {
  const panel = $("#panel-avanzada");
  panel.hidden = !panel.hidden;
  $("#btn-avanzada").classList.toggle("active", !panel.hidden);
});

$("#btn-limpiar-filtros").addEventListener("click", () => {
  $("#filtro-rango").value = "";
  $("#filtro-titulo").value = "";
  $("#filtro-articulo").value = "";
  $("#filtro-materia").value = "";
  $("#lista-leyes").innerHTML = "";
});

$("#btn-buscar-avanzada").addEventListener("click", busquedaAvanzada);

async function busquedaAvanzada() {
  const params = new URLSearchParams();
  const q = $("#buscar").value.trim();
  const rango = $("#filtro-rango").value;
  const titulo = $("#filtro-titulo").value.trim();
  const articulo = $("#filtro-articulo").value.trim();
  const materia = $("#filtro-materia").value.trim();
  if (q) params.set("q", q);
  if (rango) params.set("rango", rango);
  if (titulo) params.set("titulo", titulo);
  if (articulo) params.set("articulo", articulo);
  if (materia) params.set("materia", materia);
  params.set("limit", "100");

  const lista = $("#lista-leyes");
  lista.innerHTML = '<div class="empty">Buscando…</div>';

  const res = await fetch(`/api/catalogo?${params}`);
  const data = await res.json();
  if (!data.items.length) {
    lista.innerHTML = '<div class="empty">No se encontraron normas con esos filtros.</div>';
    return;
  }
  const total = data.total;
  lista.innerHTML = `<div class="meta" style="margin-bottom:.5rem">${total} resultado${total !== 1 ? "s" : ""}</div>`;
  const contenedor = document.createElement("div");
  contenedor.innerHTML = data.items
    .map(
      (item) => `
    <div class="ley-item" data-id="${item.identificador}">
      <div class="titulo-ley">${escHtml(item.titulo || item.identificador)}</div>
      <div class="meta">${escHtml(item.rango || "")}</div>
    </div>`
    )
    .join("");
  contenedor.querySelectorAll(".ley-item").forEach((el) => {
    el.addEventListener("click", () => cargarLey(el.dataset.id));
  });
  lista.appendChild(contenedor);
}

/* ─── Event listeners ─── */
let debounce;
$("#buscar").addEventListener("input", () => {
  clearTimeout(debounce);
  debounce = setTimeout(buscarLeyes, 300);
});

let debounceCat;
$("#buscar-cat").addEventListener("input", () => {
  clearTimeout(debounceCat);
  debounceCat = setTimeout(filtrarCategoria, 300);
});

let debounceArea;
$("#buscar-area")?.addEventListener("input", () => {
  clearTimeout(debounceArea);
  debounceArea = setTimeout(filtrarArea, 300);
});

let debounceArt;
$("#buscar-art").addEventListener("input", () => {
  clearTimeout(debounceArt);
  debounceArt = setTimeout(() => renderArticulosLey($("#buscar-art").value.trim()), 200);
});

$("#btn-simular").addEventListener("click", simularReforma);
$("#btn-restaurar").addEventListener("click", () => {
  $("#texto-reforma").value = state.textoVigente;
});
$$(".tab").forEach((el) => {
  el.addEventListener("click", () => activarTab(el.dataset.tab));
});
["perfil-situacion", "perfil-ingresos", "perfil-hogar"].forEach((id) => {
  document.getElementById(id).addEventListener("change", () => {
    if (state.articuloId) cargarArticulo(state.articuloId);
  });
});

/* ─── Init ─── */
$("#btn-auth-login").addEventListener("click", () => {
  $("#modal-auth").hidden = true;
  mostrarPanel("comunidad");
  const tab = document.querySelector('#auth-box .auth-tab[data-auth="login"]');
  if (tab) mostrarAuthTab("login");
});

$("#btn-auth-registrarme").addEventListener("click", () => {
  $("#modal-auth").hidden = true;
  mostrarPanel("comunidad");
  const tab = document.querySelector('#auth-box .auth-tab[data-auth="registro"]');
  if (tab) mostrarAuthTab("registro");
});

async function arrancarSesion() {
  setAuthBloqueo(true);
  try {
    const data = await (await fetch("/api/sesion", { credentials: "same-origin" })).json();
    if (data.autenticado) {
      aplicarSesion(data);
      await restaurarNavegacionGuardada();
      return;
    }
  } catch {}
  localStorage.removeItem("rg_uid");
  localStorage.removeItem("rg_username");
  localStorage.removeItem("rg_nombre_visible");
  actualizarSesionUI();
  setAuthBloqueo(true);
  const params = new URLSearchParams(location.search);
  const reset = params.get("reset");
  if (reset) {
    $("#reset-token").value = reset;
    $("#modal-auth").hidden = true;
    mostrarPanel("comunidad");
    mostrarAuthTab("recuperar");
  } else {
    setTimeout(() => {
      if (authBloqueo) $("#modal-auth").hidden = false;
    }, 400);
    cargarCaptcha("login");
  }
}

cargarAreas();
cargarCategorias();
cargarColecciones();
irInicio();
mostrarBtnGuardar();
actualizarSesionUI();
arrancarSesion();

/* ─── Service Worker con aviso de actualización ─── */
if ("serviceWorker" in navigator) {
  let swNuevo = null;

  navigator.serviceWorker.register("/sw.js").then((reg) => {
    if (reg.waiting) {
      mostrarAvisoActualizacion(reg.waiting);
    }

    reg.addEventListener("updatefound", () => {
      const instalando = reg.installing;
      if (!instalando) return;
      instalando.addEventListener("statechange", () => {
        if (instalando.state === "installed" && navigator.serviceWorker.controller) {
          mostrarAvisoActualizacion(instalando);
        }
      });
    });

    // Comprobar actualizaciones cada 60 segundos
    setInterval(() => reg.update(), 60_000);
  }).catch(() => {});

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (swNuevo) location.reload();
  });

  function mostrarAvisoActualizacion(worker) {
    swNuevo = worker;
    const banner = $("#banner-update");
    if (banner) banner.hidden = false;
  }

  document.addEventListener("click", (e) => {
    if (e.target.id === "btn-update-si") {
      if (swNuevo) swNuevo.postMessage("SKIP_WAITING");
      const banner = $("#banner-update");
      if (banner) banner.hidden = true;
    }
    if (e.target.id === "btn-update-no") {
      const banner = $("#banner-update");
      if (banner) banner.hidden = true;
    }
  });
}

/* ─── Compartir ─── */
let enlaceSeleccionado = location.origin;

let enlacePublicoGuardado = "";

function esEnlacePublico(url) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    if (host.endsWith(".trycloudflare.com") || host.endsWith(".loca.lt") || host.endsWith(".lhr.life")) {
      return true;
    }
    if (enlacePublicoGuardado) {
      const guardadoHost = new URL(enlacePublicoGuardado).hostname.toLowerCase();
      if (host === guardadoHost) return true;
    }
    return location.protocol === "https:" && host === location.hostname.toLowerCase() && !host.startsWith("127.");
  } catch {
    return false;
  }
}

function enlacePublicoVivo() {
  if (location.protocol === "https:" && esEnlacePublico(location.origin)) {
    return location.origin;
  }
  return null;
}

async function abrirCompartir() {
  const modal = $("#modal-compartir");
  const lista = $("#lista-enlaces");
  const qr = $("#qr-compartir");
  const aviso = $("#aviso-enlace-compartir");
  lista.innerHTML = '<div class="empty">Obteniendo enlaces…</div>';
  if (aviso) aviso.hidden = true;
  modal.hidden = false;
  try {
    const data = await (await fetch("/api/acceso")).json();
    enlacePublicoGuardado = data.publico || "";
    const items = [];
    const vivo = enlacePublicoVivo();
    const publico = vivo || data.publico || null;

    if (publico) {
      items.push({ etiqueta: "Enlace público (internet)", url: publico });
    }
    (data.red_local || []).forEach((url) => {
      items.push({ etiqueta: "Misma Wi‑Fi", url });
    });
    if (!publico && (data.este_equipo || []).length) {
      items.push({ etiqueta: "Solo este PC", url: data.este_equipo[0] });
    }
    if (!items.length) {
      items.push({ etiqueta: "Esta página", url: location.origin });
    }

    enlaceSeleccionado = publico || items[0].url;
    if (aviso) aviso.hidden = Boolean(publico && data.tunel_activo !== false);

    lista.innerHTML = items
      .map(
        (item) => `
      <div class="enlace-item${item.url === enlaceSeleccionado ? " activo" : ""}" data-url="${item.url}">
        <strong>${item.etiqueta}</strong>
        <a href="${item.url}" target="_blank" rel="noopener">${item.url}</a>
      </div>`
      )
      .join("");

    lista.querySelectorAll(".enlace-item").forEach((el) => {
      el.addEventListener("click", () => {
        enlaceSeleccionado = el.dataset.url;
        lista.querySelectorAll(".enlace-item").forEach((n) => n.classList.toggle("activo", n === el));
      });
    });

    qr.src = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(enlaceSeleccionado)}`;
    qr.hidden = false;
  } catch {
    lista.innerHTML = `<div class="enlace-item activo" data-url="${location.origin}"><strong>Esta página</strong><a href="${location.origin}">${location.origin}</a></div>`;
    enlaceSeleccionado = location.origin;
    if (aviso) aviso.hidden = false;
  }
}

$("#btn-compartir").addEventListener("click", abrirCompartir);
$("#btn-cerrar-compartir").addEventListener("click", () => {
  $("#modal-compartir").hidden = true;
});
$("#btn-copiar").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(enlaceSeleccionado);
    $("#btn-copiar").textContent = "Copiado";
    setTimeout(() => {
      $("#btn-copiar").textContent = "Copiar enlace";
    }, 1500);
  } catch {
    prompt("Copia este enlace:", enlaceSeleccionado);
  }
});

/* ─── Comunidad ─── */
function uid() {
  return localStorage.getItem("rg_uid") || "";
}

function guardarUid(id) {
  if (id) localStorage.setItem("rg_uid", id);
}

function guardarUsername(name) {
  if (name) localStorage.setItem("rg_username", name);
}

function guardarNombreVisible(name) {
  if (name != null) localStorage.setItem("rg_nombre_visible", name);
}

function getNombreVisible() {
  return localStorage.getItem("rg_nombre_visible") || "";
}

function getUsername() {
  return localStorage.getItem("rg_username") || "";
}

function actualizarSesionUI() {
  const u = uid();
  const uname = getUsername();
  const authBox = $("#auth-box");
  const sesionInfo = $("#sesion-info");
  if (u && uname) {
    if (authBox) authBox.hidden = true;
    if (sesionInfo) {
      sesionInfo.hidden = false;
      $("#sesion-nombre").textContent = uname;
    }
  } else {
    if (authBox) authBox.hidden = false;
    if (sesionInfo) sesionInfo.hidden = true;
  }
}

// Tabs auth
function mostrarAuthTab(tipo) {
  $$("#auth-box .auth-tab").forEach((t) => t.classList.toggle("active", t.dataset.auth === tipo));
  $("#auth-login").hidden = tipo !== "login";
  $("#auth-registro").hidden = tipo !== "registro";
  $("#auth-recuperar").hidden = tipo !== "recuperar";
  $("#auth-cambiar-pass").hidden = tipo !== "cambiar-pass";
  if (tipo === "login") cargarCaptcha("login");
  if (tipo === "registro") cargarCaptcha("registro");
  if (tipo === "recuperar") {
    const hayReset = !!($("#reset-token")?.value);
    $("#form-recuperar").hidden = hayReset;
    $("#form-restablecer").hidden = !hayReset;
    cargarCaptcha(hayReset ? "restablecer" : "recuperar");
  }
  if (tipo === "cambiar-pass") cargarCaptcha("cambiar-pass");
}

$$("#auth-box .auth-tab").forEach((el) => {
  el.addEventListener("click", () => mostrarAuthTab(el.dataset.auth));
});

$("#btn-cerrar-sesion").addEventListener("click", () => limpiarSesion());

function pintarComunidad(data) {
  if (!data) return;
  $("#stat-usuarios").textContent = data.usuarios_registrados ?? "0";
  $("#stat-visitas").textContent = data.visitas_totales ?? "0";
  $("#stat-media").textContent = data.valoraciones ? `${data.puntuacion_media} / 5` : "—";
  const lista = $("#lista-sugerencias");
  const items = data.sugerencias || [];
  if (!items.length) {
    lista.className = "empty";
    lista.textContent = "Aún no hay sugerencias.";
    return;
  }
  lista.className = "";
  lista.innerHTML = items
    .map(
      (s) => `
    <div class="sugerencia">
      <div class="metric-label"><strong>${escHtml(s.nombre || "Anónimo")}</strong><span>${"★".repeat(s.puntuacion || 0)}${"☆".repeat(5 - (s.puntuacion || 0))}</span></div>
      <p style="margin:.35rem 0 0;">${escHtml(s.sugerencia || "")}</p>
    </div>`
    )
    .join("");
}

async function cargarComunidad() {
  try {
    const data = await (await fetch("/api/comunidad")).json();
    pintarComunidad(data);
  } catch {}
}

fetch("/api/visita", {
  method: "POST",
  credentials: "same-origin",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ dispositivo: navigator.userAgent }),
})
  .then((r) => r.json())
  .then((data) => {
    pintarComunidad(data);
  })
  .catch(() => cargarComunidad());

// Login
$("#form-login").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = $("#msg-login");
  msg.textContent = "";
  const res = await apiFetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: $("#login-user").value,
      password: $("#login-pass").value,
      ...captchaPayload("login"),
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    msg.textContent = data.error || "Error al iniciar sesión.";
    cargarCaptcha("login");
    return;
  }
  aplicarSesion(data);
  msg.textContent = "";
});

// Registro
$("#form-registro").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = $("#msg-registro");
  msg.textContent = "";
  const res = await apiFetch("/api/registro", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nombre: $("#reg-nombre").value,
      username: $("#reg-username").value,
      password: $("#reg-password").value,
      email: $("#reg-email").value,
      dispositivo: navigator.userAgent,
      ...captchaPayload("registro"),
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    msg.textContent = data.error || "No se pudo registrar.";
    cargarCaptcha("registro");
    return;
  }
  aplicarSesion(data);
  msg.textContent = data.nuevo ? "Registro completado. ¡Bienvenido!" : `Hola de nuevo, ${data.nombre}.`;
});

// Recuperar contraseña
$("#form-recuperar").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = $("#msg-recuperar");
  msg.textContent = "";
  const res = await apiFetch("/api/recuperar-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: $("#rec-email").value,
      ...captchaPayload("recuperar"),
    }),
  });
  const data = await res.json();
  cargarCaptcha("recuperar");
  if (!res.ok) {
    msg.textContent = data.error || "No se pudo enviar el enlace.";
    return;
  }
  msg.textContent = data.aviso
    ? `${data.mensaje} (${data.aviso})`
    : (data.mensaje || "Revisa tu correo.");
});

$("#form-restablecer").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = $("#msg-restablecer");
  msg.textContent = "";
  const nueva = $("#reset-pass").value;
  if (nueva !== $("#reset-pass-2").value) {
    msg.textContent = "Las contraseñas no coinciden.";
    return;
  }
  const res = await apiFetch("/api/restablecer-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      token: $("#reset-token").value,
      password_nuevo: nueva,
      ...captchaPayload("restablecer"),
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    msg.textContent = data.error || "No se pudo restablecer.";
    cargarCaptcha("restablecer");
    return;
  }
  $("#reset-token").value = "";
  history.replaceState({}, "", "/");
  aplicarSesion(data);
  msg.textContent = "Contraseña actualizada. Sesión iniciada.";
});

// Cambiar contraseña (sin sesión)
$("#form-cambiar-pass").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = $("#msg-cambiar-pass");
  msg.textContent = "";
  const nueva = $("#cp-pass-nueva").value;
  const repetir = $("#cp-pass-repetir").value;
  if (nueva !== repetir) {
    msg.textContent = "Las contraseñas nuevas no coinciden.";
    return;
  }
  if (nueva.length < 8) {
    msg.textContent = "La contraseña nueva debe tener al menos 8 caracteres.";
    return;
  }
  const res = await apiFetch("/api/cambiar-contrasena", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: $("#cp-user").value.trim().toLowerCase(),
      password_actual: $("#cp-pass-actual").value,
      password_nuevo: nueva,
      ...captchaPayload("cambiar-pass"),
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    msg.textContent = data.error || "No se pudo cambiar la contraseña.";
    cargarCaptcha("cambiar-pass");
    return;
  }
  $("#cp-pass-actual").value = "";
  $("#cp-pass-nueva").value = "";
  $("#cp-pass-repetir").value = "";
  aplicarSesion(data);
  msg.textContent = "Contraseña actualizada. Ya has iniciado sesión.";
  mostrarAuthTab("login");
});

$("#form-valoracion").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = $("#msg-valoracion");
  const res = await apiFetch("/api/valoracion", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nombre: getNombreVisible() || $("#reg-nombre").value || "Anónimo",
      puntuacion: Number($("#val-puntos").value),
      sugerencia: $("#val-texto").value,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    msg.textContent = data.error || "No se pudo enviar.";
    return;
  }
  pintarComunidad(data);
  $("#val-texto").value = "";
  msg.textContent = "Valoración enviada. Gracias.";
});

/* ─── Instalación PWA ─── */
let instalacion;

function esIOS() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function esAppInstalada() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

function yaInstalada() {
  return esAppInstalada();
}

function esHttps() {
  return location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1";
}

function mostrarInstalar() {
  const modal = $("#modal-instalar");
  const texto = $("#texto-instalar");
  const pasos = $("#pasos-instalar");
  const btnAhora = $("#btn-instalar-ahora");
  const iconoSafari = $("#icono-safari-share");
  btnAhora.hidden = true;
  iconoSafari.hidden = true;
  pasos.innerHTML = "";

  if (yaInstalada()) {
    texto.textContent = "La app ya está instalada.";
    modal.hidden = false;
    return;
  }

  if (instalacion) {
    texto.textContent = "Puedes dejarla en la pantalla de inicio como una aplicación.";
    btnAhora.hidden = false;
    modal.hidden = false;
    return;
  }

  if (esIOS()) {
    iconoSafari.hidden = false;
    texto.textContent = "En iPhone hay que usar Safari:";
    pasos.innerHTML = `
      <li>Cierra esta ventana.</li>
      <li>Abajo del todo en Safari, pulsa el cuadrado con flecha hacia arriba.</li>
      <li><strong>Baja del todo</strong> hasta ver <strong>Añadir a pantalla de inicio</strong>.</li>
      <li>Si no aparece: pulsa <strong>Editar acciones</strong> y actívala.</li>
      <li>Pulsa <strong>Añadir</strong>.</li>`;
    modal.hidden = false;
    return;
  }

  if (!esHttps()) {
    texto.textContent = "Solo se puede instalar desde el enlace público (https). Usa Compartir para ver el enlace.";
    modal.hidden = false;
    return;
  }

  texto.textContent = "En Android se añade desde el navegador:";
  pasos.innerHTML = `
    <li>Abre esta página en <strong>Chrome</strong>.</li>
    <li>Pulsa el menú <strong>⋮</strong> (arriba a la derecha).</li>
    <li>Elige <strong>Instalar aplicación</strong> o <strong>Añadir a pantalla de inicio</strong>.</li>`;
  modal.hidden = false;
}

window.addEventListener("beforeinstallprompt", (evento) => {
  evento.preventDefault();
  instalacion = evento;
});

window.addEventListener("appinstalled", () => {
  instalacion = null;
  $("#modal-instalar").hidden = true;
});

if (esIOS() && !yaInstalada()) {
  const aviso = $("#aviso-ios");
  if (aviso) aviso.hidden = false;
}

if (yaInstalada()) {
  const btnInstalar = $("#btn-instalar");
  if (btnInstalar) btnInstalar.hidden = true;
}

$("#btn-instalar").addEventListener("click", mostrarInstalar);
$("#btn-cerrar-instalar").addEventListener("click", () => {
  $("#modal-instalar").hidden = true;
});
$("#btn-instalar-ahora").addEventListener("click", async () => {
  if (!instalacion) return;
  instalacion.prompt();
  await instalacion.userChoice;
  instalacion = null;
  $("#modal-instalar").hidden = true;
});

/* ─── GUARDAR Y PERFIL ─── */

function mostrarBtnGuardar() {
  const u = uid();
  if (u) {
    $("#btn-mi-perfil").hidden = false;
  }
}

async function guardarEnPerfil(tipo, datos) {
  if (!uid()) { alert("Regístrate primero en Comunidad."); return; }
  const res = await apiFetch("/api/guardar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tipo, datos }),
  }).then((r) => r.json());
  if (res.error) { alert(res.error); return; }
  alert("Guardado en tu perfil.");
}

// Guardar simulación
$("#btn-guardar-sim").addEventListener("click", () => {
  if (!state.impactoActual || !state.leyId || !state.articuloId) return;
  guardarEnPerfil("simulacion", {
    ley_id: state.leyId,
    articulo_id: state.articuloId,
    titulo: $("#titulo-articulo").textContent,
    impacto: state.impactoActual,
    fecha: new Date().toISOString(),
  });
});

// Guardar artículo
$("#btn-guardar-art").addEventListener("click", () => {
  if (!state.leyId || !state.articuloId) return;
  guardarEnPerfil("articulo", {
    ley_id: state.leyId,
    articulo_id: state.articuloId,
    titulo: $("#titulo-articulo").textContent,
    texto_breve: (state.textoVigente || "").substring(0, 200),
    fecha: new Date().toISOString(),
  });
});

// Perfil
$("#btn-mi-perfil").addEventListener("click", abrirPerfil);
$("#btn-cerrar-perfil").addEventListener("click", cerrarPerfil);

async function abrirPerfil() {
  if (!uid()) return;
  $("#vista-perfil").hidden = false;
  $("#vista-comunidad-principal").hidden = true;

  const data = await apiFetch("/api/perfil").then((r) => r.json());
  if (data.error) {
    $("#perfil-info").innerHTML = `<p class="empty">${escHtml(data.error)}</p>`;
    return;
  }

  const u = data.usuario;
  $("#perfil-info").innerHTML = `
    <div class="perfil-card">
      <div class="perfil-avatar">👤</div>
      <div>
        <h3 style="margin:0">${escHtml(u.nombre)}</h3>
        <p class="meta">Registrado: ${u.alta ? new Date(u.alta).toLocaleDateString("es-ES") : "—"}</p>
      </div>
    </div>
    <div class="perfil-stats">
      <div class="stat"><strong>${data.resumen.guardados}</strong><span>Guardados</span></div>
      <div class="stat"><strong>${data.resumen.hilos}</strong><span>Hilos</span></div>
      <div class="stat"><strong>${data.resumen.respuestas}</strong><span>Respuestas</span></div>
      <div class="stat"><strong>${data.resumen.valoraciones}</strong><span>Valoraciones</span></div>
      <div class="stat"><strong>${data.total_visitas}</strong><span>Visitas</span></div>
    </div>`;

  // Rellenar ajustes con los datos actuales
  $("#aj-nombre").value = u.nombre || "";
  $("#aj-email").value = u.email || "";
  $("#aj-username").value = u.username || "";
  $("#aj-pass-actual").value = "";
  $("#aj-pass-nueva").value = "";
  $("#msg-ajustes").textContent = "";

  renderGuardados("simulacion", data.guardados.filter((g) => g.tipo === "simulacion"), "#perfil-simulaciones");
  renderGuardados("articulo", data.guardados.filter((g) => g.tipo === "articulo"), "#perfil-articulos");
  renderPerfilHilos(data.hilos);
  renderPerfilValoraciones(data.valoraciones);
}

function renderGuardados(tipo, items, selector) {
  const cont = $(selector);
  if (!items.length) {
    cont.className = "empty";
    cont.textContent = tipo === "simulacion" ? "No hay simulaciones guardadas." : "No hay artículos guardados.";
    return;
  }
  cont.className = "";
  cont.innerHTML = items
    .map((g) => {
      const d = g.datos || {};
      const fecha = d.fecha ? new Date(d.fecha).toLocaleDateString("es-ES") : "";
      return `
      <div class="guardado-item">
        <div class="guardado-info">
          <div class="guardado-titulo">${escHtml(d.titulo || "Sin título")}</div>
          <div class="meta">${fecha}${d.texto_breve ? " — " + escHtml(String(d.texto_breve).substring(0, 80)) + "…" : ""}</div>
          ${d.impacto ? `<div class="meta">Intensidad: ${escHtml(String(d.impacto.intensidad))}% | ${escHtml(d.impacto.signo || "mixto")}</div>` : ""}
        </div>
        <button type="button" class="btn-eliminar-guardado" data-id="${g.id}" title="Eliminar">🗑️</button>
      </div>`;
    })
    .join("");
  cont.querySelectorAll(".btn-eliminar-guardado").forEach((el) => {
    el.addEventListener("click", async () => {
      await apiFetch("/api/guardar/eliminar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: el.dataset.id }),
      });
      abrirPerfil();
    });
  });
}

function renderPerfilHilos(hilos) {
  const cont = $("#perfil-hilos");
  if (!hilos.length) { cont.className = "empty"; cont.textContent = "No hay hilos."; return; }
  cont.className = "";
  cont.innerHTML = hilos
    .map((h) => `<div class="guardado-item"><div class="guardado-titulo">${escHtml(h.titulo)}</div><div class="meta">${escHtml(h.categoria)} · ${h.fecha ? new Date(h.fecha).toLocaleDateString("es-ES") : ""}</div></div>`)
    .join("");
}

function renderPerfilValoraciones(vals) {
  const cont = $("#perfil-valoraciones");
  if (!vals.length) { cont.className = "empty"; cont.textContent = "No hay valoraciones."; return; }
  cont.className = "";
  cont.innerHTML = vals
    .map((v) => `<div class="guardado-item"><div class="guardado-titulo">${"★".repeat(v.puntuacion || 0)}${"☆".repeat(5 - (v.puntuacion || 0))}</div><div class="meta">${escHtml((v.sugerencia || "").substring(0, 100))}</div></div>`)
    .join("");
}

function cerrarPerfil() {
  $("#vista-perfil").hidden = true;
  $("#vista-comunidad-principal").hidden = false;
}

// Ajustes de cuenta
$("#form-ajustes").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("#msg-ajustes");
  msg.textContent = "";
  const res = await apiFetch("/api/perfil/actualizar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nombre: $("#aj-nombre").value,
      email: $("#aj-email").value,
      username: $("#aj-username").value,
      password_actual: $("#aj-pass-actual").value,
      password_nuevo: $("#aj-pass-nueva").value,
    }),
  }).then((r) => r.json());
  if (res.error) {
    msg.textContent = res.error;
    return;
  }
  msg.textContent = "Cambios guardados.";
  await abrirPerfil();
});

function tiempoRelativo(iso) {
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.floor(ms / 60000);
  if (min < 1) return "ahora";
  if (min < 60) return `hace ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `hace ${h}h`;
  const d = Math.floor(h / 24);
  return `hace ${d}d`;
}

function on(el, evt, fn) {
  if (el) el.addEventListener(evt, fn);
}

/* ─── COMENTARIOS EN LEYES Y ARTÍCULOS ─── */
const EMOJIS_REACCION = ["👍", "👎", "❤️", "💡", "😮", "😡", "🤔"];
const comentariosState = { leyId: "", articuloId: "", scope: "" };

function idsComentarios(scope) {
  if (scope === "art") {
    return {
      lista: "#lista-comentarios-art",
      form: "#form-comentario-art",
      input: "#input-comentario-art",
      msg: "#msg-comentario-art",
    };
  }
  return {
    lista: "#lista-comentarios-ley",
    form: "#form-comentario-ley",
    input: "#input-comentario-ley",
    msg: "#msg-comentario-ley",
  };
}

function renderBarraEmojis(comentario) {
  const reacciones = comentario.reacciones || {};
  return EMOJIS_REACCION.map((emoji) => {
    const count = reacciones[emoji] || 0;
    const activo = comentario.mi_reaccion === emoji ? " activo" : "";
    const countHtml = count ? `<span class="emoji-count">${count}</span>` : `<span class="emoji-count"></span>`;
    return `<button type="button" class="emoji-btn${activo}" data-comentario="${comentario.id}" data-emoji="${emoji}" title="Reaccionar">${emoji}${countHtml}</button>`;
  }).join("");
}

function renderListaComentarios(scope, comentarios) {
  const { lista } = idsComentarios(scope);
  const cont = $(lista);
  if (!cont) return;

  if (!comentarios.length) {
    cont.innerHTML = '<div class="empty">Sé el primero en opinar sobre esta norma.</div>';
    return;
  }

  cont.innerHTML = comentarios
    .map(
      (c) => `
    <article class="comentario-item" data-id="${c.id}">
      <p class="comentario-meta"><strong>${escHtml(c.autor)}</strong> · ${tiempoRelativo(c.fecha)}</p>
      <div class="comentario-cuerpo">${escHtml(c.cuerpo)}</div>
      <div class="emoji-bar">${renderBarraEmojis(c)}</div>
    </article>`
    )
    .join("");

  cont.querySelectorAll(".emoji-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!uid()) {
        alert("Regístrate o inicia sesión para reaccionar.");
        return;
      }
      const res = await foroPost("/api/comentarios/reaccion", {
        comentario_id: btn.dataset.comentario,
        emoji: btn.dataset.emoji,
      });
      if (res.error) {
        alert(res.error);
        return;
      }
      recargarComentariosActuales();
    });
  });
}

async function cargarComentarios(scope, leyId, articuloId, leyTitulo, articuloTitulo) {
  comentariosState.scope = scope;
  comentariosState.leyId = leyId;
  comentariosState.articuloId = articuloId || "";
  comentariosState.leyTitulo = leyTitulo || "";
  comentariosState.articuloTitulo = articuloTitulo || "";

  const { lista } = idsComentarios(scope);
  const cont = $(lista);
  if (cont) cont.innerHTML = '<div class="empty">Cargando opiniones…</div>';

  const params = new URLSearchParams({ ley_id: leyId });
  if (articuloId) params.set("articulo_id", articuloId);

  try {
    const res = await apiFetch(`/api/comentarios?${params}`);
    const data = await res.json();
    if (!res.ok) {
      if (cont) cont.innerHTML = `<div class="empty">${escHtml(data.error || "No se pudieron cargar las opiniones.")}</div>`;
      return;
    }
    renderListaComentarios(scope, data.comentarios || []);
  } catch {
    if (cont) cont.innerHTML = '<div class="empty">Error al cargar opiniones. Recarga la página.</div>';
  }
}

function recargarComentariosActuales() {
  const { scope, leyId, articuloId, leyTitulo, articuloTitulo } = comentariosState;
  if (!leyId || !scope) return;
  cargarComentarios(scope, leyId, articuloId, leyTitulo, articuloTitulo);
}

function enviarComentario(scope, e) {
  e.preventDefault();
  const { input, msg } = idsComentarios(scope);
  const msgEl = $(msg);
  msgEl.textContent = "";
  if (!uid()) {
    msgEl.textContent = "Regístrate o inicia sesión para comentar.";
    return;
  }
  const cuerpo = $(input).value.trim();
  if (cuerpo.length < 3) {
    msgEl.textContent = "Escribe al menos 3 caracteres.";
    return;
  }

  const articuloId = scope === "art" ? comentariosState.articuloId : "";
  const articuloTitulo = scope === "art" ? comentariosState.articuloTitulo : "";

  foroPost("/api/comentarios", {
    ley_id: comentariosState.leyId,
    articulo_id: articuloId,
    cuerpo,
    ley_titulo: comentariosState.leyTitulo || "",
    articulo_titulo: articuloTitulo,
  }).then((res) => {
    if (res.error) {
      msgEl.textContent = res.error;
      return;
    }
    $(input).value = "";
    msgEl.textContent = "Comentario publicado.";
    cargarComentarios(
      scope,
      comentariosState.leyId,
      articuloId,
      comentariosState.leyTitulo,
      articuloTitulo
    );
    setTimeout(() => {
      if (msgEl.textContent === "Comentario publicado.") msgEl.textContent = "";
    }, 2500);
  });
}

$("#form-comentario-art")?.addEventListener("submit", (e) => enviarComentario("art", e));

const enlaceOpiniones = $("#enlace-opiniones");
if (enlaceOpiniones) {
  enlaceOpiniones.addEventListener("click", (e) => {
    e.preventDefault();
    const seccion = $("#seccion-comentarios-art");
    if (seccion && !seccion.hidden) {
      seccion.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
}

$("#form-comentario-ley")?.addEventListener("submit", (e) => enviarComentario("ley", e));

/* ─── FORO ─── */
const foroState = { catActual: "", hiloAbierto: null };

function foroPost(url, body) {
  return apiFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => r.json());
}

async function cargarHilos(cat) {
  foroState.catActual = cat || "";
  const params = cat ? `?categoria=${encodeURIComponent(cat)}` : "";
  const hilos = await (await fetch(`/api/foro/hilos${params}`)).json();
  const cont = $("#foro-hilos");
  if (!hilos.length) {
    cont.innerHTML = '<div class="empty">No hay hilos todavía. ¡Sé el primero!</div>';
    return;
  }
  cont.innerHTML = hilos
    .map(
      (h) => `
    <div class="foro-hilo-card" data-id="${h.id}">
      <div class="foro-votos">
        <button type="button" class="voto-btn voto-up" data-target="${h.id}" data-tipo="up">▲</button>
        <span class="voto-num">${h.puntos}</span>
        <button type="button" class="voto-btn voto-down" data-target="${h.id}" data-tipo="down">▼</button>
      </div>
      <div class="foro-hilo-info">
        <span class="foro-cat-badge">${escHtml(h.categoria)}</span>
        <div class="foro-hilo-titulo">${escHtml(h.titulo)}</div>
        <div class="foro-hilo-meta">
          <span>${escHtml(h.autor)}</span> · <span>${tiempoRelativo(h.fecha)}</span> · <span>${h.respuestas} respuesta${h.respuestas !== 1 ? "s" : ""}</span>
        </div>
      </div>
    </div>`
    )
    .join("");
  cont.querySelectorAll(".foro-hilo-card").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target.classList.contains("voto-btn")) return;
      abrirHilo(el.dataset.id);
    });
  });
  cont.querySelectorAll(".voto-btn").forEach((el) => {
    el.addEventListener("click", async (e) => {
      e.stopPropagation();
      const res = await foroPost("/api/foro/votar", { target_id: el.dataset.target, tipo: el.dataset.tipo });
      if (res.ok) cargarHilos(foroState.catActual);
    });
  });
}

async function abrirHilo(id) {
  foroState.hiloAbierto = id;
  $("#foro-hilos").hidden = true;
  $("#btn-nuevo-hilo").hidden = true;
  $("#foro-tabs").hidden = true;
  $("#form-hilo-box").hidden = true;
  const box = $("#foro-hilo-abierto");
  box.hidden = false;

  const hilo = await (await fetch(`/api/foro/hilo/${encodeURIComponent(id)}`)).json();
  if (hilo.error) {
    box.innerHTML = `<p class="empty">${escHtml(hilo.error)}</p>`;
    return;
  }

  $("#foro-hilo-detalle").innerHTML = `
    <div class="foro-hilo-full">
      <div class="foro-votos-inline">
        <button type="button" class="voto-btn voto-up" data-target="${escHtml(hilo.id)}" data-tipo="up">▲</button>
        <span class="voto-num">${hilo.puntos}</span>
        <button type="button" class="voto-btn voto-down" data-target="${escHtml(hilo.id)}" data-tipo="down">▼</button>
      </div>
      <span class="foro-cat-badge">${escHtml(hilo.categoria)}</span>
      <h3 style="margin:.3rem 0">${escHtml(hilo.titulo)}</h3>
      <p class="foro-hilo-meta">${escHtml(hilo.autor)} · ${tiempoRelativo(hilo.fecha)}</p>
      <div class="foro-cuerpo">${escHtml(hilo.cuerpo).replace(/\n/g, "<br>")}</div>
    </div>`;

  const resps = hilo.respuestas_lista || [];
  $("#foro-respuestas-lista").innerHTML = resps.length
    ? resps
        .map(
          (r) => `
      <div class="foro-resp">
        <div class="foro-votos-inline">
          <button type="button" class="voto-btn voto-up" data-target="${r.id}" data-tipo="up">▲</button>
          <span class="voto-num">${r.puntos}</span>
          <button type="button" class="voto-btn voto-down" data-target="${r.id}" data-tipo="down">▼</button>
        </div>
        <div>
          <p class="foro-hilo-meta"><strong>${escHtml(r.autor)}</strong> · ${tiempoRelativo(r.fecha)}</p>
          <div class="foro-cuerpo">${escHtml(r.cuerpo).replace(/\n/g, "<br>")}</div>
        </div>
      </div>`
        )
        .join("")
    : '<div class="empty">Sin respuestas todavía.</div>';

  box.querySelectorAll(".voto-btn").forEach((el) => {
    el.addEventListener("click", async () => {
      await foroPost("/api/foro/votar", { target_id: el.dataset.target, tipo: el.dataset.tipo });
      abrirHilo(id);
    });
  });
}

function cerrarHilo() {
  foroState.hiloAbierto = null;
  $("#foro-hilo-abierto").hidden = true;
  $("#foro-hilos").hidden = false;
  $("#btn-nuevo-hilo").hidden = false;
  $("#foro-tabs").hidden = false;
  cargarHilos(foroState.catActual);
}

// Eventos del foro
on($("#btn-volver-foro"), "click", cerrarHilo);

on($("#btn-nuevo-hilo"), "click", () => {
  if (!uid()) { alert("Regístrate primero en la sección superior."); return; }
  $("#form-hilo-box").hidden = !$("#form-hilo-box").hidden;
});

on($("#btn-cancelar-hilo"), "click", () => {
  $("#form-hilo-box").hidden = true;
});

on($("#form-hilo"), "submit", async (e) => {
  e.preventDefault();
  const msg = $("#msg-hilo");
  msg.textContent = "";
  const res = await foroPost("/api/foro/hilo", {
    titulo: $("#hilo-titulo").value,
    cuerpo: $("#hilo-cuerpo").value,
    categoria: $("#hilo-cat").value,
  });
  if (res.error) { msg.textContent = res.error; return; }
  $("#hilo-titulo").value = "";
  $("#hilo-cuerpo").value = "";
  $("#form-hilo-box").hidden = true;
  cargarHilos(foroState.catActual);
});

on($("#form-respuesta"), "submit", async (e) => {
  e.preventDefault();
  const msg = $("#msg-respuesta");
  msg.textContent = "";
  if (!uid()) { msg.textContent = "Regístrate primero."; return; }
  const res = await foroPost("/api/foro/respuesta", {
    hilo_id: foroState.hiloAbierto,
    cuerpo: $("#resp-cuerpo").value,
  });
  if (res.error) { msg.textContent = res.error; return; }
  $("#resp-cuerpo").value = "";
  abrirHilo(foroState.hiloAbierto);
});

function seleccionarTabForo(cat, tabEl) {
  const categoria = cat || "";
  foroState.catActual = categoria;
  $$("#foro-tabs .foro-tab").forEach((t) => {
    const activo = t === tabEl;
    t.classList.toggle("active", activo);
    t.setAttribute("aria-selected", activo ? "true" : "false");
  });
  const lbl = $("#foro-filtro-label");
  if (lbl) {
    lbl.innerHTML = categoria
      ? `Mostrando: <strong>${escHtml(categoria)}</strong>`
      : "Mostrando: <strong>Todos</strong>";
  }
  cargarHilos(categoria);
}

function initForoTabs() {
  const cont = $("#foro-tabs");
  if (!cont) return;
  let ultimoClick = 0;
  cont.querySelectorAll(".foro-tab").forEach((tab) => {
    tab.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const ahora = Date.now();
      if (ahora - ultimoClick < 250) return;
      ultimoClick = ahora;
      seleccionarTabForo(tab.dataset.cat || "", tab);
    });
  });
}

initForoTabs();
cargarHilos("");
