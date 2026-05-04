'use strict';

(function () {
  const toggle  = document.getElementById('schema-toggle');
  const panel   = document.getElementById('schema-panel');
  const content = document.getElementById('schema-content');

  let loaded = false;

  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', String(!open));
    panel.hidden = open;
    if (!open && !loaded) loadSchema();
  });

  async function loadSchema() {
    try {
      const res    = await fetch('/api/schema');
      const schema = await res.json();
      content.innerHTML = renderSchema(schema);
      loaded = true;
    } catch (_) {
      content.innerHTML = '<p style="color:var(--color-muted);font-size:.875rem">Could not load schema.</p>';
    }
  }

  function renderSchema(schema) {
    const parts = [];

    parts.push(renderTable('Workout (top level)', schema.properties, schema.required || []));

    const defs = schema.$defs || {};
    if (defs.WorkoutStep) {
      parts.push(renderTable('WorkoutStep', defs.WorkoutStep.properties, defs.WorkoutStep.required || []));
    }
    if (defs.Duration) {
      parts.push(renderOneOf('Duration variants', defs.Duration.oneOf || []));
    }
    if (defs.Target) {
      parts.push(renderOneOf('Target variants', defs.Target.oneOf || []));
    }

    return parts.join('');
  }

  function renderTable(title, props, required) {
    if (!props) return '';
    const rows = Object.entries(props).map(([name, def]) => {
      const isReq  = required.includes(name);
      const type   = describeType(def);
      const desc   = def.description || '';
      const enums  = def.enum ? def.enum.map((v) => `<code>${v}</code>`).join(' ') : '';
      return `
        <tr>
          <td><span class="schema-field-name">${name}</span>${isReq ? '<span class="schema-required">required</span>' : ''}</td>
          <td class="schema-type">${type}</td>
          <td>${desc}${enums ? `<div class="schema-enum">${enums}</div>` : ''}</td>
        </tr>`;
    }).join('');

    return `
      <p class="schema-section-title">${title}</p>
      <table class="schema-table">
        <thead><tr><th>Field</th><th>Type</th><th>Description / Values</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  function renderOneOf(title, variants) {
    if (!variants.length) return '';
    const rows = variants.map((v) => {
      const typeConst = v.properties?.type?.const || '?';
      const others    = Object.entries(v.properties || {})
        .filter(([k]) => k !== 'type')
        .map(([k, d]) => `<span class="schema-field-name">${k}</span> <span class="schema-type">(${describeType(d)})</span>`)
        .join(', ');
      return `
        <tr>
          <td><code>${typeConst}</code></td>
          <td>${others || '<em>no extra fields</em>'}</td>
        </tr>`;
    }).join('');

    return `
      <p class="schema-section-title">${title}</p>
      <table class="schema-table">
        <thead><tr><th>type</th><th>Additional fields</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  function describeType(def) {
    if (!def) return '';
    if (def.$ref) return def.$ref.split('/').pop();
    if (def.type === 'string' && def.maxLength) return `string (max ${def.maxLength})`;
    if (def.type === 'number' || def.type === 'integer') {
      const parts = [];
      if (def.minimum !== undefined) parts.push(`min ${def.minimum}`);
      if (def.maximum !== undefined) parts.push(`max ${def.maximum}`);
      return `${def.type}${parts.length ? ' (' + parts.join(', ') + ')' : ''}`;
    }
    if (def.type === 'array') return 'array';
    return def.type || '';
  }
})();
