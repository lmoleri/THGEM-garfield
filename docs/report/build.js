const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + __dirname + '/report.html', {waitUntil: 'networkidle'});
  await p.waitForSelector('body[data-ready="1"]');
  await p.pdf({ path: process.argv[2] || (__dirname + '/THGEM_anode_signal_report.pdf'), format: 'A4', printBackground: true, preferCSSPageSize: true,
    displayHeaderFooter: true, headerTemplate: '<div></div>',
    footerTemplate: '<div style="width:100%;font-size:7.5pt;font-family:Inter,DejaVu Sans,sans-serif;color:#77756f;padding:0 19mm;display:flex;justify-content:space-between"><span>THGEM anode signal study · 11 Nov 2026</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>' });
  await b.close();
})();
