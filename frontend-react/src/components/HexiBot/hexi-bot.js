/**
 * HexiBot Chatbot Avatar Component & Controller
 * Base states (Idle, Happy) + Searching (Complete 30-Hexagon Grid with Customizable loops)
 * Theme support: Light & Dark
 */

(function (global) {
  function hp(cx, cy, r) {
    var p = [];
    for (var i = 0; i < 6; i++) {
      var a = (60 * i * Math.PI) / 180;
      p.push((cx + r * Math.cos(a)).toFixed(1) + ',' + (cy + r * Math.sin(a)).toFixed(1));
    }
    return p.join(' ');
  }

  // Generate complete 30-cell outer hexagon grid (rings 2 & 3)
  var R = 13, S3 = Math.sqrt(3), cells = [], hits = [3, 11, 19, 27];
  for (var q = -3; q <= 3; q++) {
    for (var r = -3; r <= 3; r++) {
      var ring = Math.max(Math.abs(q), Math.abs(r), Math.abs(q + r));
      if (ring < 2 || ring > 3) continue;
      cells.push({ x: 100 + 1.5 * R * q, y: 95 + S3 * R * (r + q / 2), ring: ring });
    }
  }

  var gridPolygonsHtml = cells.map(function (c, i) {
    var h = hits.indexOf(i) > -1;
    return '<polygon class="kc' + (h ? ' hit' : '') + '" style="--r:' + (c.ring == 2 ? .1 : .22) + 's;--d:-' + (((i * 7 + 3) % 11) / 11 * 1.2).toFixed(2) + 's" points="' + hp(c.x, c.y, R * .92) + '"/>';
  }).join('');

  var len = [22, 17, 21, 12], textLinesHtml = '', chipsHtml = '';
  len.forEach(function (w, j) {
    var y = 8 + 11 * j;
    textLinesHtml += '<line class="kln" style="--ld:' + (.15 * j).toFixed(2) + 's" x1="170" y1="' + y + '" x2="' + (170 + w) + '" y2="' + y + '"/>';
  });

  hits.forEach(function (ix, j) {
    var c = cells[ix];
    if (c) {
      chipsHtml += '<g transform="translate(' + c.x.toFixed(1) + ' ' + c.y.toFixed(1) + ')"><polygon class="kchip2" style="--x:' + (164 - c.x).toFixed(1) + 'px;--y:' + (8 + 11 * j - c.y).toFixed(1) + 'px" points="' + hp(0, 0, R * .92) + '"/></g>';
    }
  });

  var HexiStyles = `
    :host { display: inline-block; width: 200px; height: 190px; }
    .hexi-wrapper { width: 100%; height: 100%; position: relative; }
    .hexi-wrapper[data-theme="light"] { --bg: #ffffff; --fg: #000000; }
    .hexi-wrapper[data-theme="dark"] { --bg: #000000; --fg: #ffffff; }
    @media (prefers-color-scheme: dark) {
      .hexi-wrapper:not([data-theme="light"]) { --bg: #000000; --fg: #ffffff; }
    }
    .hex { fill: var(--bg); stroke: var(--fg); stroke-width: 7; stroke-linejoin: round; }
    .f { fill: var(--fg); }
    .s { fill: none; stroke: var(--fg); stroke-width: 6; stroke-linecap: round; stroke-linejoin: round; }
    .bot, .kg { width: 100%; height: 100%; display: block; overflow: visible; }
    
    /* Base States */
    .bot .tilt { transform-origin: 100px 95px; }
    .bot .fg { animation: fl 4s ease-in-out infinite; }
    .bot .eye, .bot .mouth, .bot .hy { transform-box: fill-box; transform-origin: center; }
    .bot .hy { opacity: 0; }
    .bot.blink .eye { transform: scaleY(.1); }
    
    .bot[data-state=happy] .eye { opacity: 0; }
    .bot[data-state=happy] .hy { opacity: 1; }
    .bot[data-state=happy] .mouth { transform: scale(1.35); }
    .bot[data-state=happy] .fg { animation: hopl 1.6s ease-out infinite; }
    
    .bot[data-state=talk] .mouth, .bot[data-state=talking] .mouth { animation: kmt .4s ease-in-out infinite alternate; }
    .bot[data-state=talk] .look, .bot[data-state=talking] .look { animation: scanS 1.2s ease-in-out infinite alternate; }
    .bot[data-state=talk] .fg, .bot[data-state=talking] .fg { animation: fl 2s ease-in-out infinite; }
    
    /* Searching Sequence (Knowledge Hexagon Grid) */
    .kg .hex { fill: var(--bg); }
    .kg .eye, .kg .mouth { transform-box: fill-box; transform-origin: center; }
    .kg .mouth { transform: scale(.7,.2); }
    .kc { fill: var(--fg); fill-opacity: 0; stroke: var(--fg); stroke-width: 1.6; stroke-opacity: .3; stroke-linejoin: round; }
    
    .kseq .kzoom { transform-box: view-box; transform-origin: 100px 95px; }
    .kseq .kgrid { opacity: 0; transform-box: view-box; transform-origin: 100px 95px; }
    .kchip2 { fill: var(--fg); opacity: 0; }
    .kln { fill: none; stroke: var(--fg); stroke-width: 4; stroke-linecap: round; transform-box: fill-box; transform-origin: left center; opacity: 0; transform: scaleX(0); }
    .kcur { fill: none; stroke: var(--fg); stroke-width: 2; stroke-linejoin: round; opacity: 0; }
    
    .kseq[data-ph=start] .kzoom { animation: kzo .5s ease-in-out forwards; }
    .kseq[data-ph=lookup] .kzoom { transform: scale(.32); }
    .kseq[data-ph=answer] .kzoom { transform: scale(.32); animation: kzb .5s ease-in-out .4s forwards; }
    .kseq[data-ph=start] .kgrid { animation: kgi .5s ease-out forwards; }
    .kseq[data-ph=lookup] .kgrid { opacity: 1; }
    .kseq[data-ph=answer] .kgrid { opacity: 1; animation: kgo .5s ease-in .4s forwards; }
    .kseq[data-ph=start] .kc { animation: kring .5s ease-out both; animation-delay: var(--r); }
    .kseq[data-ph=lookup] .kc { animation: kflick 1.2s ease-in-out infinite; animation-delay: var(--d); }
    .kseq[data-ph=answer] .kc.hit { animation: khit .4s ease-out forwards; }
    .kseq[data-ph=start] .look, .kseq[data-ph=lookup] .look { animation: scanS6 1.2s ease-in-out infinite alternate; }
    .kseq[data-ph=answer] .look { animation: klook .9s ease-in-out forwards; }
    .kseq[data-ph=answer] .mouth { animation: kmo .9s ease-in-out forwards; }
    .kseq[data-ph=answer] .kchip2 { animation: kchip .5s ease-in-out .3s both; }
    .kseq[data-ph=talk] .kchip2, .kseq[data-ph=done] .kchip2 { opacity: 1; transform: translate(var(--x),var(--y)) scale(.32); }
    .kseq[data-ph=talk] .kln { animation: kloop 1.2s ease-in-out infinite; animation-delay: var(--ld); }
    .kseq[data-ph=done] .kln { opacity: 1; transform: scaleX(1); }
    .kseq[data-ph=talk] .look { animation: scanS 1.2s ease-in-out infinite alternate; }
    .kseq[data-ph=talk] .mouth { animation: kmt .6s ease-in-out infinite alternate; }
    .kseq[data-ph=done] .mouth { transform: scale(1.3,1.3); }
    .kseq[data-ph=done] .kcur { animation: kcb .7s steps(1) infinite; }

    @keyframes kzo { from { transform: scale(1); } to { transform: scale(.32); } }
    @keyframes kzb { from { transform: scale(.32); } to { transform: scale(1); } }
    @keyframes kgi { from { opacity: 0; transform: scale(2.4); } to { opacity: 1; transform: scale(1); } }
    @keyframes kgo { from { opacity: 1; transform: scale(1); } to { opacity: 0; transform: scale(2.4); } }
    @keyframes kring { 0%,100% { fill-opacity: 0; stroke-opacity: .3; } 50% { fill-opacity: .85; stroke-opacity: 1; } }
    @keyframes kflick { 0%,100% { fill-opacity: 0; stroke-opacity: .3; } 40% { fill-opacity: .7; stroke-opacity: 1; } }
    @keyframes khit { from { fill-opacity: 0; stroke-opacity: .3; } to { fill-opacity: 1; stroke-opacity: 1; } }
    @keyframes scanS6 { from { transform: translateX(-6px); } to { transform: translateX(6px); } }
    @keyframes klook { 0% { transform: translate(0,0); } 25% { transform: translate(3px,-5px); } 50% { transform: translate(8px,-3px); } 75% { transform: translate(3px,0); } 100% { transform: translate(0,0); } }
    @keyframes kmo { 0% { transform: scale(.7,.2); } 15% { transform: scale(1,.9); } 30% { transform: scale(.7,.3); } 45% { transform: scale(1,.9); } 60% { transform: scale(.7,.3); } 75%,100% { transform: scale(1,.9); } }
    @keyframes kmt { from { transform: scale(.7,.3); } to { transform: scale(1,.9); } }
    @keyframes kchip { 0% { opacity: 0; transform: translate(0,0) scale(1); } 15% { opacity: 1; } 100% { opacity: 1; transform: translate(var(--x),var(--y)) scale(.32); } }
    @keyframes kloop { 0% { opacity: 1; transform: scaleX(0); } 40%,85% { opacity: 1; transform: scaleX(1); } 100% { opacity: 1; transform: scaleX(0); } }
    @keyframes kcb { 0%,100% { opacity: 1; } 50% { opacity: 0; } }
    @keyframes fl { 50% { transform: translateY(-3px); } }
    @keyframes hopl { 0%,40%,100% { transform: translateY(0); } 20% { transform: translateY(-10px); } }
    @keyframes scanS { from { transform: translateX(-3px); } to { transform: translateX(3px); } }
  `;

  class HexiBotElement extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._state = 'idle';
      this._theme = 'light';
      this._searchTimer = null;
      this._blinkTimer = null;
    }

    connectedCallback() {
      this.render();
      this.startBlinkLoop();
      if (this.hasAttribute('state')) this.setState(this.getAttribute('state'));
      if (this.hasAttribute('theme')) this.setTheme(this.getAttribute('theme'));
    }

    disconnectedCallback() {
      clearTimeout(this._searchTimer);
      clearTimeout(this._blinkTimer);
    }

    static get observedAttributes() { return ['state', 'theme']; }

    attributeChangedCallback(name, oldVal, newVal) {
      if (oldVal === newVal) return;
      if (name === 'state') this.setState(newVal);
      if (name === 'theme') this.setTheme(newVal);
    }

    setTheme(theme) {
      this._theme = theme;
      var wrap = this.shadowRoot.querySelector('.hexi-wrapper');
      if (wrap) wrap.setAttribute('data-theme', theme);
    }

    setState(state) {
      this._state = state;
      clearTimeout(this._searchTimer);
      var wrap = this.shadowRoot.querySelector('.hexi-wrapper');
      if (!wrap) return;

      if (state === 'searching' || state === 'search') {
        this.runSearchSequence({});
        return;
      }

      wrap.innerHTML = this.getBotSVGHtml(state);
    }

    /**
     * Run customizable search sequence
     * @param {Object} opts - { lookupLoops: number, textLoops: number, onComplete: function }
     */
    runSearchSequence(opts) {
      var self = this;
      var lookupLoops = opts.lookupLoops || 2;
      var textLoops = opts.textLoops || 2;
      var wrap = this.shadowRoot.querySelector('.hexi-wrapper');

      wrap.innerHTML = this.getSearchSVGHtml();
      var svg = wrap.querySelector('.kg');

      function setPhase(ph) {
        svg.removeAttribute('data-ph');
        void svg.getBoundingClientRect();
        svg.setAttribute('data-ph', ph);
      }

      // Step 1: Start Phase (0.5s)
      setPhase('start');
      this._searchTimer = setTimeout(function () {
        // Step 2: Lookup Phase (customizable loops * 1.2s)
        setPhase('lookup');
        self._searchTimer = setTimeout(function () {
          // Step 3: Answer Phase (0.9s hit highlights)
          setPhase('answer');
          self._searchTimer = setTimeout(function () {
            // Step 4: Talk Phase (customizable text line loops * 1.2s)
            setPhase('talk');
            self._searchTimer = setTimeout(function () {
              // Step 5: Done
              setPhase('done');
              if (opts.onComplete) opts.onComplete();
            }, textLoops * 1200);
          }, 900);
        }, lookupLoops * 1200);
      }, 500);
    }

    getBotSVGHtml(state) {
      return `
        <svg class="bot" data-state="${state}" viewBox="0 0 200 190" aria-hidden="true">
          <g class="tilt">
            <g class="fg">
              <polygon class="hex" points="${hp(100, 95, 82)}"/>
              <g class="look">
                <circle class="f eye eL" cx="76" cy="84" r="8"/>
                <circle class="f eye eR" cx="124" cy="84" r="8"/>
              </g>
              <g class="hy">
                <path class="s" d="M64 90 Q76 70 88 90"/>
                <path class="s" d="M112 90 Q124 70 136 90"/>
              </g>
              <path class="s mouth" d="M84 122 Q100 134 116 122"/>
            </g>
          </g>
        </svg>
      `;
    }

    getSearchSVGHtml() {
      return `
        <svg class="kg kseq" data-ph="idle" viewBox="0 0 200 190" aria-hidden="true">
          <g class="kgrid">${gridPolygonsHtml}</g>
          <g class="kzoom">
            <polygon class="hex" points="${hp(100, 95, 82)}"/>
            <g class="look">
              <circle class="f eye" cx="76" cy="84" r="8"/>
              <circle class="f eye" cx="124" cy="84" r="8"/>
            </g>
            <path class="s mouth" d="M84 122 Q100 134 116 122"/>
          </g>
          ${chipsHtml}
          ${textLinesHtml}
          <polygon class="kcur" points="${hp(188, 41, 3.8)}"/>
        </svg>
      `;
    }

    startBlinkLoop() {
      var self = this;
      (function blink() {
        self._blinkTimer = setTimeout(function () {
          var bot = self.shadowRoot.querySelector('.bot[data-state=idle]');
          if (bot) {
            bot.classList.add('blink');
            setTimeout(function () { if (bot) bot.classList.remove('blink'); }, 140);
          }
          blink();
        }, 2000 + Math.random() * 3000);
      })();
    }

    render() {
      this.shadowRoot.innerHTML = `
        <style>${HexiStyles}</style>
        <div class="hexi-wrapper" data-theme="${this._theme}">
          ${this.getBotSVGHtml(this._state)}
        </div>
      `;
    }
  }

  if (!customElements.get('hexi-bot')) {
    customElements.define('hexi-bot', HexiBotElement);
  }

  global.HexiBot = HexiBotElement;
})(window);
