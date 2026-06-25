const https = require('https');

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'content-type, x-api-key');

  if (req.method === 'OPTIONS') return res.status(204).end();

  const apiKey = req.headers['x-api-key'];
  if (!apiKey) return res.status(400).json({ error: { message: 'Missing API key' } });

  const body = JSON.stringify(req.body);

  return new Promise((resolve) => {
    const options = {
      hostname: 'api.anthropic.com',
      path: '/v1/messages',
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'content-length': Buffer.byteLength(body),
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-allow-browser': 'true',
      },
    };

    const proxy = https.request(options, (upstream) => {
      let data = '';
      upstream.on('data', (chunk) => { data += chunk; });
      upstream.on('end', () => {
        res.setHeader('content-type', 'application/json');
        res.status(upstream.statusCode).send(data);
        resolve();
      });
    });

    proxy.on('error', (e) => {
      res.status(500).json({ error: { message: e.message } });
      resolve();
    });

    proxy.write(body);
    proxy.end();
  });
};
