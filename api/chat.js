module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'content-type, x-api-key');

  if (req.method === 'OPTIONS') return res.status(204).end();

  try {
    const apiKey = req.headers['x-api-key'];
    if (!apiKey) return res.status(400).json({ error: { message: 'Missing x-api-key header' } });

    const upstream = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-allow-browser': 'true',
      },
      body: JSON.stringify(req.body),
    });

    const data = await upstream.text();
    res.setHeader('content-type', 'application/json');
    return res.status(upstream.status).send(data);
  } catch (e) {
    return res.status(500).json({ error: { message: e.message } });
  }
};
