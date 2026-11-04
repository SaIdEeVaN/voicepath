-- VoicePath -- national schemes, and the trades they name.
-- Apply after 009_document_source_url.sql. Safe to re-run.
--
-- Generated from backend/app/data/catalogue.py, which stays the source of
-- truth for the offline catalogue; tests/test_catalogue_sync.py checks the two
-- agree.
--
-- 1. schemes.skill_match. "all" (every existing row): the work needs every
--    listed skill, weighted -- a welding job. "any": one listed trade is enough.
--    PM Vishwakarma covers eighteen trades and a tailor fits it fully; under
--    "all" she scored 0.05 and was filtered out. See matching.skill_similarity.
--
-- 2. Twenty-four skills: PM Vishwakarma's trades not already in the taxonomy
--    (its official release, PIB 1959098, lists all eighteen), and the work
--    PM SVANidhi, NAMASTE and the training schemes name -- street vending,
--    sanitation work, waste collection, handloom, solar, fishing, food
--    processing, domestic work. They have no embedding until one is computed;
--    the API computes missing ones at startup (services/corpus_sync.py), and
--    until then normalization simply cannot reach them, which is the safe
--    failure.
--
-- 3. Eleven national schemes, location "All India". Every description is
--    sentences copied exactly from the official release in official_url --
--    the explanation layer may ground itself only in this text -- and
--    tests/test_national_schemes.py checks each sentence against the copy of
--    that release in backend/data/scheme_docs.
--
-- Stand-Up India is not here: its last official extension ran to 2025 and no
-- release confirms it is still open.

-- ---------------------------------------------------------------------------
-- 1. skill_match
-- ---------------------------------------------------------------------------
alter table schemes add column if not exists skill_match text not null default 'all';

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'schemes_skill_match_allowed'
  ) then
    alter table schemes add constraint schemes_skill_match_allowed
      check (skill_match in ('all', 'any'));
  end if;
end $$;

comment on column schemes.skill_match is
  'all: the work needs every listed skill (weighted). any: one listed trade is enough.';

-- ---------------------------------------------------------------------------
-- 2. skill_taxonomy
-- ---------------------------------------------------------------------------
insert into skill_taxonomy (code, name, category, hint, aliases) values
  ('SK034', 'Solar Panel Installation', 'Electrical',
   'Fitting and wiring rooftop solar panels.',
   '["solar panel fitting","solar installer","rooftop solar","solar technician","सोलर पैनल लगाना","सोलर मिस्त्री","சோலார் பேனல் பொருத்துதல்","சோலார் வேலை"]'),
  ('SK055', 'Handloom Weaving', 'Textile',
   'Weaving cloth on a hand-operated loom.',
   '["handloom","weaver","hand weaving","saree weaving","हथकरघा","बुनकर","कपड़ा बुनना","கைத்தறி","நெசவு","நெசவாளர்","தறி நெய்தல்"]'),
  ('SK064', 'Food Processing', 'Hospitality',
   'Making pickles, papad, snacks, spice powders and similar food for sale.',
   '["pickle making","papad making","snacks making","masala powder","अचार बनाना","पापड़ बनाना","नमकीन बनाना","ஊறுகாய் தயாரித்தல்","அப்பளம் தயாரித்தல்","மசாலா பொடி"]'),
  ('SK075', 'Fishing', 'Agriculture',
   'Catching fish from sea, river or pond, by boat or net.',
   '["fisherman","fishing","fish catching","boat fishing","मछली पकड़ना","मछुआरा","மீன்பிடித்தல்","மீனவர்","மீன் பிடிப்பு"]'),
  ('SK095', 'Street Vending', 'Commerce',
   'Selling goods or food from a cart, stall or footpath, or moving place to place.',
   '["street vendor","hawker","cart vendor","vegetable vendor","fruit seller","tea stall","ठेला","रेहड़ी","फेरीवाला","सब्ज़ी बेचना","தள்ளுவண்டி வியாபாரம்","தெருவோர வியாபாரம்","காய்கறி விற்பனை","டீ கடை"]'),
  ('SK113', 'Barbering', 'Service',
   'Haircuts and shaving.',
   '["barber","hair cutting","shaving","naai","saloon","नाई","बाल काटना","हजामत","முடி திருத்துதல்","நாவிதர்","சவரம்","முடி வெட்டுதல்"]'),
  ('SK114', 'Washing and Ironing', 'Service',
   'Laundry -- washing, starching and ironing clothes.',
   '["washerman","dhobi","laundry","ironing","press wala","धोबी","कपड़े धोना","इस्त्री","प्रेस करना","சலவை","வண்ணார்","இஸ்திரி","துணி துவைத்தல்"]'),
  ('SK115', 'Sanitation Work', 'Service',
   'Cleaning sewers, septic tanks, drains and public toilets.',
   '["sanitation worker","sewer cleaning","septic tank cleaning","drain cleaning","safai karamchari","सफ़ाई कर्मचारी","सीवर सफ़ाई","सेप्टिक टैंक सफ़ाई","துப்புரவுப் பணி","சாக்கடை சுத்தம்","செப்டிக் டேங்க் சுத்தம்","துப்புரவுத் தொழிலாளி"]'),
  ('SK116', 'Waste Collection and Recycling', 'Service',
   'Collecting and sorting waste, scrap and recyclables.',
   '["waste picker","rag picker","scrap collection","kabadi","garbage collection","कचरा बीनना","कबाड़","कबाड़ी","குப்பை சேகரிப்பு","பழைய பொருள் சேகரிப்பு","மறுசுழற்சி"]'),
  ('SK117', 'Domestic Work', 'Service',
   'Cooking, cleaning and caring in other people''s homes.',
   '["house maid","domestic help","house help","cook in houses","घरेलू काम","घर का काम","बाई","வீட்டு வேலை","வீட்டுப் பணியாளர்"]'),
  ('SK121', 'Boat Making', 'Traditional Crafts',
   'Building and repairing wooden boats.',
   '["boat maker","boat building","boat repair","नाव बनाना","नाव बनाने वाला","படகு கட்டுதல்","படகு செய்தல்"]'),
  ('SK122', 'Armourer (Traditional)', 'Traditional Crafts',
   'Forging traditional weapons, armour and metal implements.',
   '["armourer","armorer","weapon making","अस्त्र बनाना","हथियार बनाने वाला","ஆயுதம் செய்தல்"]'),
  ('SK123', 'Blacksmithing', 'Traditional Crafts',
   'Forging iron -- farm tools, implements, repairs.',
   '["blacksmith","lohar","iron work","forging","लोहार","लोहे का काम","கொல்லர்","கொல்லர் வேலை","இரும்பு அடித்தல்"]'),
  ('SK124', 'Hammer and Tool Kit Making', 'Traditional Crafts',
   'Making hand tools such as hammers, chisels and sickles.',
   '["tool maker","hammer making","hand tool making","औज़ार बनाना","हथौड़ा बनाना","கருவி செய்தல்","சுத்தியல் செய்தல்"]'),
  ('SK125', 'Locksmithing', 'Traditional Crafts',
   'Making and repairing locks and keys.',
   '["locksmith","key making","duplicate key","lock repair","ताला चाबी","चाबी बनाना","ताला बनाना","பூட்டு சாவி","சாவி செய்தல்","பூட்டு பழுது"]'),
  ('SK126', 'Goldsmithing', 'Traditional Crafts',
   'Making and repairing gold and silver jewellery.',
   '["goldsmith","jewellery making","jeweller","sonar","सुनार","गहने बनाना","பொற்கொல்லர்","ஆசாரி","நகை செய்தல்","நகை வேலை"]'),
  ('SK127', 'Pottery', 'Traditional Crafts',
   'Shaping and firing clay pots, lamps and tiles.',
   '["potter","kumhar","clay pots","pot making","कुम्हार","मिट्टी के बर्तन","குயவர்","மண்பாண்டம்","மண்பானை செய்தல்"]'),
  ('SK128', 'Sculpture and Stone Carving', 'Traditional Crafts',
   'Carving idols and figures in stone or other material.',
   '["sculptor","stone carver","idol making","moortikar","मूर्तिकार","मूर्ति बनाना","पत्थर तराशना","சிற்பி","சிற்ப வேலை","கல் செதுக்குதல்"]'),
  ('SK129', 'Stone Breaking', 'Traditional Crafts',
   'Breaking and dressing stone by hand, in quarries or on site.',
   '["stone breaker","quarry work","stone cutting","पत्थर तोड़ना","पत्थर तोड़ने का काम","கல் உடைத்தல்","கல் உடைப்பு","குவாரி வேலை"]'),
  ('SK130', 'Footwear Making and Repair', 'Traditional Crafts',
   'Making and mending shoes and sandals; leather work.',
   '["cobbler","shoe repair","shoemaker","chappal repair","leather work","मोची","जूते बनाना","जूता मरम्मत","செருப்பு தைத்தல்","காலணி பழுது","தோல் வேலை"]'),
  ('SK131', 'Basket, Mat, Broom and Coir Weaving', 'Traditional Crafts',
   'Weaving baskets, mats and brooms; coir rope and products.',
   '["basket weaving","mat weaving","broom making","coir work","bamboo work","टोकरी बुनना","चटाई बुनना","झाड़ू बनाना","கூடை முடைதல்","பாய் நெய்தல்","துடைப்பம் செய்தல்","கயிறு திரித்தல்"]'),
  ('SK132', 'Traditional Doll and Toy Making', 'Traditional Crafts',
   'Making dolls and toys by hand in wood, clay or cloth.',
   '["toy maker","doll making","wooden toys","खिलौने बनाना","गुड़िया बनाना","பொம்மை செய்தல்","மரப்பொம்மை"]'),
  ('SK133', 'Garland Making', 'Traditional Crafts',
   'Stringing flower garlands for sale, temples and functions.',
   '["garland maker","flower garland","malakar","flower stringing","माला बनाना","फूलों की माला","மாலை கட்டுதல்","பூ கட்டுதல்","பூமாலை"]'),
  ('SK134', 'Fishing Net Making', 'Traditional Crafts',
   'Knotting and mending fishing nets.',
   '["net maker","net mending","fishing net","जाल बनाना","मछली का जाल","வலை பின்னுதல்","மீன் வலை"]')
on conflict (code) do update
  set name     = excluded.name,
      category = excluded.category,
      hint     = excluded.hint,
      aliases  = excluded.aliases;

with labels (code, names) as (values
  ('SK034', '{"ta": "சோலார் பேனல் பொருத்துதல்", "hi": "सोलर पैनल लगाना"}'),
  ('SK055', '{"ta": "கைத்தறி நெசவு", "hi": "हथकरघा बुनाई"}'),
  ('SK064', '{"ta": "உணவுப் பதப்படுத்துதல்", "hi": "खाद्य प्रसंस्करण"}'),
  ('SK075', '{"ta": "மீன்பிடித்தல்", "hi": "मछली पकड़ना"}'),
  ('SK095', '{"ta": "தெருவோர வியாபாரம்", "hi": "रेहड़ी-पटरी पर बिक्री"}'),
  ('SK113', '{"ta": "முடி திருத்துதல்", "hi": "नाई का काम"}'),
  ('SK114', '{"ta": "சலவை மற்றும் இஸ்திரி", "hi": "कपड़े धोना और इस्त्री"}'),
  ('SK115', '{"ta": "துப்புரவுப் பணி", "hi": "सफ़ाई का काम"}'),
  ('SK116', '{"ta": "குப்பை சேகரிப்பு மற்றும் மறுசுழற்சி", "hi": "कचरा संग्रह और रीसाइक्लिंग"}'),
  ('SK117', '{"ta": "வீட்டு வேலை", "hi": "घरेलू काम"}'),
  ('SK121', '{"ta": "படகு கட்டுதல்", "hi": "नाव बनाना"}'),
  ('SK122', '{"ta": "பாரம்பரிய ஆயுதம் செய்தல்", "hi": "पारंपरिक अस्त्र बनाना"}'),
  ('SK123', '{"ta": "கொல்லர் வேலை", "hi": "लोहार का काम"}'),
  ('SK124', '{"ta": "சுத்தியல் மற்றும் கருவி செய்தல்", "hi": "हथौड़ा और औज़ार बनाना"}'),
  ('SK125', '{"ta": "பூட்டு சாவி வேலை", "hi": "ताला-चाबी का काम"}'),
  ('SK126', '{"ta": "பொற்கொல்லர் வேலை", "hi": "सुनार का काम"}'),
  ('SK127', '{"ta": "மண்பாண்டம் செய்தல்", "hi": "मिट्टी के बर्तन बनाना"}'),
  ('SK128', '{"ta": "சிற்ப வேலை", "hi": "मूर्ति और पत्थर की नक्काशी"}'),
  ('SK129', '{"ta": "கல் உடைத்தல்", "hi": "पत्थर तोड़ना"}'),
  ('SK130', '{"ta": "காலணி செய்தல் மற்றும் பழுது", "hi": "जूते बनाना और मरम्मत"}'),
  ('SK131', '{"ta": "கூடை, பாய், துடைப்பம், கயிறு வேலை", "hi": "टोकरी, चटाई, झाड़ू और रस्सी का काम"}'),
  ('SK132', '{"ta": "பாரம்பரிய பொம்மை செய்தல்", "hi": "पारंपरिक खिलौने बनाना"}'),
  ('SK133', '{"ta": "மாலை கட்டுதல்", "hi": "माला बनाना"}'),
  ('SK134', '{"ta": "மீன்பிடி வலை பின்னுதல்", "hi": "मछली का जाल बनाना"}')
)
update skill_taxonomy t
   set display_names = jsonb_build_object('en', t.name) || l.names::jsonb
  from labels l
 where t.code = l.code;

-- ---------------------------------------------------------------------------
-- 3. schemes -- inserted once each, keyed on source_reference; a re-run
-- brings the text of existing rows back in step with the catalogue.
-- ---------------------------------------------------------------------------
with c (title, organization, location, district, type, source_reference,
        official_url, description, skill_match) as (values
  ('PM Vishwakarma',
   'Ministry of Micro, Small & Medium Enterprises',
   'All India', 'All India', 'Self-employment support', 'GOI/PMVISHWAKARMA/2023-09-20',
   'https://pmvishwakarma.gov.in/',
   'PM Vishwakarma, a Central Sector Scheme, was launched on 17 th September, 2023 by the Prime Minister to provide end-to-end support to artisans and craftspeople who work with their hands and tools. Skill Upgradation : Basic Training of 5-7 days and Advanced Training of 15 days or more, with a stipend of Rs. 500 per day; Toolkit Incentive : A toolkit incentive of upto Rs. 15,000 in the form of e-vouchers at the beginning of Basic Skill Training. Credit Support : Collateral free ‘Enterprise Development Loans’ of upto Rs. 3 lakh in two tranches of Rs. 1 lakh and Rs. 2 lakh with tenures of 18 months and 30 months, respectively, at a concessional rate of interest fixed at 5%, with Government of India subvention to the extent of 8%. Enrolment of beneficiaries shall be done through Common Service Centres with Aadhaar-based biometric authentication on PM Vishwakarma portal.',
   'any'),
  ('Pradhan Mantri Kaushal Vikas Yojana 4.0 (PMKVY 4.0)',
   'Ministry of Skill Development and Entrepreneurship',
   'All India', 'All India', 'Training', 'GOI/PMKVY4/2025-02-07',
   'https://www.skillindiadigital.gov.in/home',
   'PMKVY 4.0 scheme provides NSQF aligned skill development training through Short-Term Training (STT) including Special Projects (SP) and reskilling and upskilling through Recognition of Prior Learning (RPL) with its target beneficiary being 15-59 years of age. A key shift under the scheme is the integration of On-the-Job Training (OJT) within short-term skilling programs, ensuring that trainees gain real-world exposure and industry experience. PMKVY 4.0 ensures industry-aligned training with curriculum available in multiple regional languages, making skilling more inclusive and accessible.',
   'any'),
  ('PM National Apprenticeship Promotion Scheme (PM-NAPS)',
   'Ministry of Skill Development and Entrepreneurship',
   'All India', 'All India', 'Apprenticeship', 'GOI/PMNAPS/2025-02-07',
   'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2100845',
   'Apprenticeship training can play a major role for on-the-job vocational training where youth can acquire skills by working at actual workplace and earn some stipend, at the same time, to financially support himself. To support both apprentices and establishments in India, 25% of the stipend, up to Rs.1,500 per month per apprentice, will be provided through Direct Benefit Transfer (DBT) during the training period, provided by the Central Government. The scheme is designed for individuals aged 14 to 35 years, ensuring inclusive access to skill development opportunities across various demographics.',
   'any'),
  ('Jan Shikshan Sansthan (JSS)',
   'Ministry of Skill Development and Entrepreneurship',
   'All India', 'All India', 'Training', 'GOI/JSS/2025-12-01',
   'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2197057',
   'The Jan Shikshan Sansthan (JSS) Scheme, initially launched as Shramik Vidyapeeth (SVP) in 1967, aims to provide skill training in a non-formal mode at the doorsteps of the beneficiary through registered Societies (NGOs) with 100% grant from the Government of India. The objective of the scheme is to increase the household income by promoting self/wage employment through skill development training. The target beneficiaries of the scheme are non-literates, neo-literates and persons having rudimentary level of education, school dropouts up to class 12th in the age group of 15-45 years. The priority groups are women, SCs, STs, OBCs and minorities in the rural areas and urban low-income areas.',
   'any'),
  ('Deen Dayal Upadhyaya Grameen Kaushalya Yojana (DDU-GKY)',
   'Ministry of Rural Development',
   'All India', 'All India', 'Training', 'GOI/DDUGKY/2026-01-01',
   'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2210378',
   'The program occupies a unique position amongst other skill training programs, due to its focus on the rural poor youth and its emphasis on sustainable employment through the prominence and incentives given to post-placement tracking, retention and career progression. Mandatory social inclusion: SC/ST (50%), Women (33%), and PwDs (5%). Minimum 70% placement (Minimum 50% wage employment and maximum 20% self employment). Salary to the placed candidates are given as per the Minimum wages or above. The target group for DDU-GKY is poor rural youth in the age group 15-35.',
   'any'),
  ('Rural Self Employment Training Institutes (RSETIs)',
   'Ministry of Rural Development, with sponsor banks',
   'All India', 'All India', 'Training', 'GOI/RSETI/2026-01-01',
   'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2210378',
   'The Rural Self Employment Training Institutes (RSETIs) are dedicated, district-level training center’s set up under the sponsorship of public sector/private banks, in collaboration with the Ministry of Rural Development (MoRD). The scheme provides free, short-term, residential training to rural youth with boarding and lodging facilities. To provide free, residential, demand-driven skill training to rural unemployed youth in the age group of 18–50 years. Post-training, trainees receive handholding support for two years to facilitate self-employment, micro-enterprise development, or wage employment, with strong emphasis on credit linkage through banks.',
   'any'),
  ('Prime Minister’s Employment Generation Programme (PMEGP)',
   'Ministry of Micro, Small & Medium Enterprises, through KVIC',
   'All India', 'All India', 'Self-employment support', 'GOI/PMEGP/2026-05-14',
   'https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/may/doc2026514869801.pdf',
   'PMEGP supports prospective entrepreneurs in establishing new micro-enterprises in the non-farm sector by providing Margin Money (MM) subsidy on bank loans. The scheme primarily aims to create self-employment opportunities for first-generation entrepreneurs and promote sustainable livelihoods in the manufacturing and services sectors, especially in rural areas. The maximum project cost eligible for Margin Money subsidy is ₹50 lakh for the manufacturing sector and ₹20 lakh for the service/business sector. For special categories, the subsidy is 35% of the project cost in rural areas. It is 25% in urban areas. Special category includes SC/ST, OBC, minorities, women, ex-servicemen, persons with disabilities, and applicants from the North-East Region, Hill and Border areas.',
   'any'),
  ('PM SVANidhi',
   'Ministry of Housing and Urban Affairs and Department of Financial Services',
   'All India', 'All India', 'Self-employment support', 'GOI/PMSVANIDHI/2026-05-30',
   'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2267102',
   'PM SVANidhi is a Central Sector Scheme supporting street vendors through affordable working capital, financial inclusion and social protection measures. The lending period has been extended until March 2030. Street vendors receive collateral-free working capital loans of ₹15,000, ₹25,000 and ₹50,000 through progressive loan tranches. PM SVANidhi encourages timely and early repayment by providing an interest subsidy of 7 percent per annum. A street vendor holding a valid Letter of Recommendation or Certificate of Vending can apply for a PM SVANidhi loan through the scheme portal or Mobile App or with the assistance of Urban Local Bodies (ULBs).',
   'any'),
  ('Pradhan Mantri MUDRA Yojana (PMMY)',
   'Ministry of Finance, through banks, RRBs, NBFCs and MFIs',
   'All India', 'All India', 'Self-employment support', 'GOI/PMMY/2026-04-08',
   'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2249915',
   'This initiative has been designed to bridge the gap in financial accessibility, offering streamlined, easy collateral-free loans up to ₹20 lakh to support small-scale business ventures for non-corporate and non-farm income-generating activities. Loans cover term financing and working capital needs across manufacturing, trading and service sectors, including activities allied to agriculture like poultry, dairy, and beekeeping, etc. The interest rate is governed by RBI guidelines, with flexible repayment terms.',
   'any'),
  ('National Action for Mechanised Sanitation Ecosystem (NAMASTE)',
   'Ministry of Social Justice and Empowerment, with the Ministry of Housing and Urban Affairs',
   'All India', 'All India', 'Self-employment support', 'GOI/NAMASTE/2026-07-20',
   'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2286726',
   'The main aim of this scheme is to ensure the safety, dignity, and social security of sanitation workers and to promote safe, machine-based sanitation across the country. Its main goal is to completely end the dangerous practice of manually cleaning sewers and septic tanks. Under the NAMASTE Scheme, sanitation workers are being identified and provided with Personal Protective Equipment (PPE) kits, health insurance, Ayushman Bharat benefits, safety training, skill development, financial support for self-employment, and access to modern sanitation machines.',
   'any'),
  ('PM-DAKSH (Pradhan Mantri Dakshata Aur Kushalta Sampann Hitgrahi Yojana)',
   'Ministry of Social Justice and Empowerment, through NSFDC, NBCFDC and NSKFDC',
   'All India', 'All India', 'Training', 'GOI/PMDAKSH/2026-03-11',
   'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2238229',
   'Pradhan Mantri Dakshata Aur Kushalta Sampann Hitgrahi Yojana (PM-DAKSH) Scheme is a Central Sector Scheme to provide skill development training to Scheduled Castes, Other Backward Communities, Economically weaker Sections, De- Notified Tribes, Safai Karamcharis including Waste Pickers through the empaneled training institutes. Under the PM-DAKSH Scheme, National Skills Qualifications Framework (NSQF) compliant, employment-oriented Skill Development Training Programmes are implemented. Upon completion of the training programmes, the trainees are extended assistance for placement in wage employment and in the case of trainees opting for self-employment, necessary guidance is provided for setting up their own ventures.',
   'any')
),
refreshed as (
  update schemes s
     set title = c.title, organization = c.organization, official_url = c.official_url,
         description = c.description, skill_match = c.skill_match
    from c
   where s.source_reference = c.source_reference
  returning s.id
)
insert into schemes (
  title, organization, location, district, type, minimum_experience,
  certifications_required, salary_min, salary_max, nsqf_level,
  source_reference, official_url, description, skill_match
)
select c.title, c.organization, c.location, c.district, c.type, 0,
       '[]'::jsonb, null, null, null,
       c.source_reference, c.official_url, c.description, c.skill_match
  from c
 where not exists (select 1 from schemes s where s.source_reference = c.source_reference);

-- ---------------------------------------------------------------------------
-- scheme_skills. Under skill_match 'any' a weight is how squarely the scheme
-- names the trade: 1.00 named in its official text, 0.40 open to any trade.
--
-- Schemes open to every trade link every skill in the taxonomy at 0.40
-- (catalogue._any_trade), raised to 1.00 where the release names the trade.
-- ---------------------------------------------------------------------------
insert into scheme_skills (scheme_id, skill_id, weight, is_essential)
select o.id, t.id, 0.40, false
from schemes o
cross join skill_taxonomy t
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
on conflict (scheme_id, skill_id) do update
  set weight = excluded.weight,
      is_essential = excluded.is_essential;

-- The trades each release names, and the schemes that name only some.
with wanted (source_reference, skill_code, weight) as (values
  ('GOI/PMEGP/2026-05-14', 'SK094', 1.00),
  ('GOI/PMMY/2026-04-08', 'SK094', 1.00),
  ('GOI/PMDAKSH/2026-03-11', 'SK115', 1.00),
  ('GOI/PMDAKSH/2026-03-11', 'SK116', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK042', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK121', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK122', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK123', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK124', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK125', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK126', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK127', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK128', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK129', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK130', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK041', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK131', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK132', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK113', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK133', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK114', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK051', 1.00),
  ('GOI/PMVISHWAKARMA/2023-09-20', 'SK134', 1.00),
  ('GOI/PMSVANIDHI/2026-05-30', 'SK095', 1.00),
  ('GOI/PMSVANIDHI/2026-05-30', 'SK113', 0.40),
  ('GOI/PMSVANIDHI/2026-05-30', 'SK130', 0.40),
  ('GOI/PMSVANIDHI/2026-05-30', 'SK114', 0.40),
  ('GOI/PMSVANIDHI/2026-05-30', 'SK091', 0.40),
  ('GOI/PMSVANIDHI/2026-05-30', 'SK061', 0.40),
  ('GOI/NAMASTE/2026-07-20', 'SK115', 1.00),
  ('GOI/NAMASTE/2026-07-20', 'SK116', 1.00)
)
insert into scheme_skills (scheme_id, skill_id, weight, is_essential)
select o.id, t.id, w.weight::numeric(3,2), false
from wanted w
join schemes o on o.source_reference = w.source_reference
join skill_taxonomy t on t.code = w.skill_code
on conflict (scheme_id, skill_id) do update
  set weight = excluded.weight,
      is_essential = excluded.is_essential;
