-- VoicePath -- skills people described that the taxonomy could not place.
-- Apply after 010_national_schemes.sql. Safe to re-run.
--
-- Generated from backend/app/data/catalogue.py, which stays the source of
-- truth; tests/test_catalogue_sync.py checks the two agree.
--
-- In production, 12 of the first 66 skills people described matched nothing.
-- Five were an engine mechanic's ("engine engine-aa velai paarthen",
-- "identifying engine problems by sound"); six were the medicine trade
-- ("Pharmacist", "pharmaceutical drug dealer" -- in India the licensed
-- wholesale trade); one was a football question. This adds:
--
-- 1. Three skills: Engine Repair and Overhaul, Pharmacy and Chemist Shop
--    Work, Medicine Sales and Distribution.
-- 2. The phrases people actually used as aliases of Engine Diagnostics. Its
--    embedding is cleared because the text it was computed from changed; the
--    API recomputes missing embeddings at startup (services/corpus_sync.py).
-- 3. Links from the schemes open to any trade, at 0.40, as 010 did for every
--    skill then in the taxonomy (catalogue._any_trade).

-- ---------------------------------------------------------------------------
-- 1 and 2. skill_taxonomy
-- ---------------------------------------------------------------------------
insert into skill_taxonomy (code, name, category, hint, aliases) values
  ('SK016', 'Engine Repair and Overhaul', 'Mechanical',
   'Opening up and rebuilding engines -- petrol and diesel, in vehicles, pumps and generators.',
   '["engine repair","engine work","engine overhaul","engine mechanic","diesel mechanic","diesel engine repair","engine rebuilding","इंजन का काम","इंजन मरम्मत","डीजल मैकेनिक","इंजन ओवरहॉल","இன்ஜின் வேலை","எஞ்சின் வேலை","இன்ஜின் ரிப்பேர்","எஞ்சின் பழுது நீக்கம்","டீசல் மெக்கானிக்"]'),
  ('SK118', 'Pharmacy and Chemist Shop Work', 'Service',
   'Dispensing medicines at a chemist''s shop or hospital pharmacy -- reading prescriptions, keeping stock and expiry dates.',
   '["pharmacist","pharmacy","pharmacy assistant","chemist","chemist shop","medical shop","medical store","medicine shop","dispensing medicines","फार्मासिस्ट","फार्मेसी","केमिस्ट","दवा की दुकान","मेडिकल स्टोर","பார்மசிஸ்ட்","மருந்தகம்","மருந்துக் கடை","மெடிக்கல் ஷாப்","மெடிக்கல் கடை"]'),
  ('SK096', 'Medicine Sales and Distribution', 'Commerce',
   'Selling and supplying medicines to chemists, clinics and hospitals -- as a medical representative or for a wholesale distributor.',
   '["medical representative","medical rep","pharmaceutical sales","pharma sales","pharmaceutical distributor","medicine distributor","pharmaceutical wholesale","pharmaceutical business","pharmaceutical drug dealer","pharmaceutical drug dealing","मेडिकल रिप्रेजेंटेटिव","दवा वितरक","दवा का थोक व्यापार","மெடிக்கல் ரெப்","மருந்து விநியோகம்","மருந்து மொத்த வியாபாரம்","பார்மசூட்டிக்கல் ட்ரக் டீலர்"]'),
  ('SK014', 'Engine Diagnostics', 'Mechanical',
   'Finding the fault -- by sound, by feel, or with a tester.',
   '["engine problem finding","engine fault","diagnose engine","engine sound","identifying engine problems by sound","engine diagnosis","finding engine problems","engine fault finding","इंजन जाँच","इंजन की दिक्कत पहचानना","इंजन की आवाज़ से खराबी पहचानना","எஞ்சின் கோளாறு கண்டறிதல்","எஞ்சின் சத்தம்","இன்ஜின் சத்தம்","இன்ஜின் கோளாறு"]')
on conflict (code) do update
  set name      = excluded.name,
      category  = excluded.category,
      hint      = excluded.hint,
      aliases   = excluded.aliases,
      -- Computed from name, category and aliases: stale once they change.
      embedding = case
        when skill_taxonomy.name is distinct from excluded.name
          or skill_taxonomy.category is distinct from excluded.category
          or skill_taxonomy.aliases is distinct from excluded.aliases
        then null
        else skill_taxonomy.embedding
      end;

with labels (code, names) as (values
  ('SK016', '{"ta": "எஞ்சின் பழுது நீக்கம்", "hi": "इंजन मरम्मत"}'),
  ('SK118', '{"ta": "மருந்தகப் பணி", "hi": "दवा दुकान का काम"}'),
  ('SK096', '{"ta": "மருந்து விற்பனை மற்றும் விநியோகம்", "hi": "दवा बिक्री और वितरण"}')
)
update skill_taxonomy t
   set display_names = jsonb_build_object('en', t.name) || l.names::jsonb
  from labels l
 where t.code = l.code;

-- ---------------------------------------------------------------------------
-- 3. scheme_skills -- the schemes open to every trade
-- ---------------------------------------------------------------------------
insert into scheme_skills (scheme_id, skill_id, weight, is_essential)
select o.id, t.id, 0.40, false
from schemes o
join skill_taxonomy t on t.code in ('SK016', 'SK118', 'SK096')
where o.source_reference in (
  'GOI/PMKVY4/2025-02-07',
  'GOI/PMNAPS/2025-02-07',
  'GOI/JSS/2025-12-01',
  'GOI/DDUGKY/2026-01-01',
  'GOI/RSETI/2026-01-01',
  'GOI/PMEGP/2026-05-14',
  'GOI/PMMY/2026-04-08',
  'GOI/PMDAKSH/2026-03-11'
)
on conflict (scheme_id, skill_id) do nothing;
