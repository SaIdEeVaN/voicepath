-- VoicePath -- seed data
-- Apply after 002_functions.sql. Safe to re-run: every insert is idempotent.
--
-- Codes SK001 / SK014 / SK022 / SK108 are fixed by the design mockup's
-- worked example (two-wheeler mechanic in Salem) -- keep them stable.
--
-- After running this, populate skill_taxonomy.embedding:
--   python -m app.scripts.embed_taxonomy      (from backend/)

-- ---------------------------------------------------------------------------
-- skill_taxonomy
-- aliases carry the spoken forms a user is likely to actually say, across
-- ta / hi / en and code-switched registers. They are embedded alongside the
-- canonical name so normalization can reach the same node from any of them.
-- ---------------------------------------------------------------------------
insert into skill_taxonomy (code, name, category, hint, aliases) values
  ('SK001', 'Two-Wheeler Repair', 'Mechanical',
   'Fixing bikes and scooters -- brakes, clutch, chain, general service.',
   '["bike repair","bike mechanic","two wheeler mechanic","scooter repair","motorcycle repair","बाइक रिपेयर","बाइक मैकेनिक","दोपहिया मरम्मत","மோட்டார் சைக்கிள் ரிப்பேர்","பைக் ரிப்பேர்","இருசக்கர வாகன பழுது"]'),
  ('SK002', 'Four-Wheeler Repair', 'Mechanical',
   'Car and light vehicle servicing.',
   '["car mechanic","car repair","four wheeler mechanic","कार मैकेनिक","गाड़ी रिपेयर","கார் மெக்கானிக்"]'),
  ('SK003', 'Heavy Vehicle Maintenance', 'Mechanical',
   'Trucks, buses and tractors.',
   '["truck mechanic","lorry repair","bus maintenance","ट्रक मैकेनिक","லாரி ரிப்பேர்"]'),
  ('SK014', 'Engine Diagnostics', 'Mechanical',
   'Finding the fault -- by sound, by feel, or with a tester.',
   '["engine problem finding","engine fault","diagnose engine","engine sound","इंजन जाँच","इंजन की दिक्कत पहचानना","எஞ்சின் கோளாறு கண்டறிதல்","எஞ்சின் சத்தம்"]'),
  ('SK015', 'Vehicle Electrical Work', 'Mechanical',
   'Wiring, battery, lights and starter on vehicles.',
   '["auto electrician","vehicle wiring","battery work","ऑटो इलेक्ट्रीशियन","வாகன வயரிங்"]'),
  ('SK022', 'Welding', 'Metalwork',
   'Joining metal. Includes arc, gas and spot welding.',
   '["welding","welder","gas welding","arc welding","वेल्डिंग","वेल्डर","வெல்டிங்"]'),
  ('SK023', 'Arc Welding', 'Metalwork',
   'Stick / MMA welding with an electrode -- gates, grills, frames.',
   '["arc welding","stick welding","MMA welding","electrode welding","आर्क वेल्डिंग","ஆர்க் வெல்டிங்"]'),
  ('SK024', 'Gas Welding', 'Metalwork',
   'Oxy-acetylene welding and cutting -- sheet metal, pipes, repairs.',
   '["gas welding","oxy welding","cutting torch","गैस वेल्डिंग","கேஸ் வெல்டிங்"]'),
  ('SK025', 'Sheet Metal Fabrication', 'Metalwork',
   'Cutting, bending and shaping sheet metal.',
   '["sheet metal","fabrication","denting","शीट मेटल","தகடு வேலை"]'),
  ('SK026', 'Lathe / Machining', 'Metalwork',
   'Turning and shaping parts on a lathe.',
   '["lathe operator","turner","machining","लेथ मशीन","லேத் ஆபரேட்டர்"]'),
  ('SK031', 'Electrical Wiring', 'Electrical',
   'House and shop wiring, switchboards, fittings.',
   '["electrician","house wiring","electric work","इलेक्ट्रीशियन","बिजली का काम","எலெக்ட்ரீஷியன்","வயரிங்"]'),
  ('SK032', 'Appliance Repair', 'Electrical',
   'Fans, mixers, motors, small household appliances.',
   '["appliance repair","motor rewinding","fan repair","मोटर रिवाइंडिंग","மோட்டார் ரிப்பேர்"]'),
  ('SK033', 'Air Conditioning and Refrigeration', 'Electrical',
   'AC and fridge installation and servicing.',
   '["AC repair","fridge repair","refrigeration","एसी रिपेयर","ஏசி ரிப்பேர்"]'),
  ('SK041', 'Masonry', 'Construction',
   'Brickwork, plastering, concrete.',
   '["mason","brick work","plastering","राजमिस्त्री","मिस्त्री","கொத்தனார்"]'),
  ('SK042', 'Carpentry', 'Construction',
   'Woodwork -- doors, windows, furniture, frames.',
   '["carpenter","wood work","furniture making","बढ़ई","लकड़ी का काम","தச்சு வேலை"]'),
  ('SK043', 'Painting (Building)', 'Construction',
   'Wall painting, putty, finishing.',
   '["painter","wall painting","पेंटर","पुताई","பெயிண்டிங்"]'),
  ('SK044', 'Plumbing', 'Construction',
   'Pipes, taps, tanks, bathroom fittings.',
   '["plumber","pipe fitting","प्लंबर","नल का काम","பிளம்பர்"]'),
  ('SK045', 'Bar Bending and Steel Fixing', 'Construction',
   'Cutting and tying reinforcement steel on site.',
   '["bar bender","steel fixer","सरिया बांधना","கம்பி வளைத்தல்"]'),
  ('SK051', 'Tailoring', 'Textile',
   'Stitching garments to measure.',
   '["tailor","stitching","sewing","दर्जी","सिलाई","தையல்"]'),
  ('SK052', 'Embroidery', 'Textile',
   'Hand and machine embroidery work.',
   '["embroidery","zari work","कढ़ाई","எம்பிராய்டரி"]'),
  ('SK053', 'Power Loom Operation', 'Textile',
   'Running and minding power looms.',
   '["power loom","loom operator","पावरलूम","விசைத்தறி"]'),
  ('SK054', 'Textile Machine Maintenance', 'Textile',
   'Keeping looms and spinning machines running.',
   '["loom mechanic","textile machine repair","लूम मैकेनिक","தறி மெக்கானிக்"]'),
  ('SK061', 'Cooking (Commercial)', 'Hospitality',
   'Cooking at scale -- hotel, canteen, catering.',
   '["cook","chef","catering","हलवाई","रसोइया","சமையல்","குக்"]'),
  ('SK062', 'Baking', 'Hospitality',
   'Bread, buns, cakes and bakery items.',
   '["baker","bakery work","बेकरी","பேக்கரி"]'),
  ('SK063', 'Housekeeping', 'Hospitality',
   'Cleaning and upkeep in hotels, hospitals, offices.',
   '["housekeeping","cleaning staff","हाउसकीपिंग","சுத்தம் செய்தல்"]'),
  ('SK071', 'Farming and Crop Production', 'Agriculture',
   'Growing crops -- sowing, irrigation, harvest.',
   '["farming","agriculture","cultivation","खेती","किसानी","விவசாயம்"]'),
  ('SK072', 'Dairy and Livestock', 'Agriculture',
   'Cattle rearing, milking, animal care.',
   '["dairy","cattle rearing","milking","डेयरी","पशुपालन","கால்நடை வளர்ப்பு"]'),
  ('SK073', 'Poultry Farming', 'Agriculture',
   'Raising chickens for eggs or meat.',
   '["poultry","chicken farming","मुर्गी पालन","கோழி வளர்ப்பு"]'),
  ('SK074', 'Farm Machinery Operation', 'Agriculture',
   'Tractors, tillers, harvesters.',
   '["tractor driving","tiller","farm machinery","ट्रैक्टर चलाना","டிராக்டர் ஓட்டுதல்"]'),
  ('SK081', 'Driving (Light Motor Vehicle)', 'Transport',
   'Driving cars, vans and small goods vehicles.',
   '["driver","car driving","LMV","ड्राइवर","गाड़ी चलाना","டிரைவர்"]'),
  ('SK082', 'Driving (Heavy Vehicle)', 'Transport',
   'Driving lorries and buses.',
   '["heavy driver","lorry driver","truck driving","ट्रक ड्राइवर","லாரி டிரைவர்"]'),
  ('SK083', 'Loading and Material Handling', 'Transport',
   'Loading, unloading and moving goods.',
   '["loading","unloading","hamali","लोडिंग","சுமை ஏற்றுதல்"]'),
  ('SK091', 'Retail Sales', 'Commerce',
   'Selling in a shop, handling customers and stock.',
   '["shop work","salesman","counter work","दुकान का काम","सेल्समैन","கடை வேலை"]'),
  ('SK092', 'Shop Bookkeeping', 'Commerce',
   'Keeping accounts and daily records for a small business.',
   '["accounts","bookkeeping","billing","हिसाब किताब","கணக்கு வேலை"]'),
  ('SK093', 'Inventory and Stock Handling', 'Commerce',
   'Tracking what comes in and goes out of a store.',
   '["stock keeping","store keeper","godown","स्टोर कीपर","சரக்கு பராமரிப்பு"]'),
  ('SK094', 'Small Business Management', 'Commerce',
   'Running your own shop or unit end to end.',
   '["own shop","self employment","business","अपना धंधा","சொந்த தொழில்"]'),
  ('SK101', 'Mobile Phone Repair', 'Electronics',
   'Screen, battery and board-level phone repair.',
   '["mobile repair","phone repair","मोबाइल रिपेयर","மொபைல் ரிப்பேர்"]'),
  ('SK102', 'Computer Hardware Repair', 'Electronics',
   'Assembling and fixing desktops and laptops.',
   '["computer repair","hardware","कंप्यूटर रिपेयर","கம்ப்யூட்டர் ரிப்பேர்"]'),
  ('SK103', 'Basic Computer Operation', 'Electronics',
   'Typing, internet, forms, basic office software.',
   '["computer knowledge","typing","MS Office","कंप्यूटर चलाना","கம்ப்யூட்டர் அறிவு"]'),
  ('SK108', 'Customer Handling', 'Service',
   'Talking to customers, understanding what they need.',
   '["customer service","talking to customers","dealing with people","ग्राहक व्यवहार","ग्राहकों से बात","வாடிக்கையாளர் கையாளுதல்","கஸ்டமர் சர்வீஸ்"]'),
  ('SK109', 'Team Supervision', 'Service',
   'Leading a small crew and organising the day''s work.',
   '["supervisor","team lead","foreman","सुपरवाइजर","மேற்பார்வையாளர்"]'),
  ('SK110', 'Security Services', 'Service',
   'Guarding premises, gate duty, patrolling.',
   '["security guard","watchman","गार्ड","चौकीदार","செக்யூரிட்டி"]'),
  ('SK111', 'Beauty and Wellness', 'Service',
   'Salon work -- hair, skin, grooming.',
   '["beautician","salon","parlour","ब्यूटीशियन","பியூட்டீஷியன்"]'),
  ('SK112', 'Healthcare Support', 'Service',
   'Assisting patients and nursing staff.',
   '["ward boy","nursing assistant","patient care","नर्सिंग सहायक","மருத்துவ உதவியாளர்"]')
on conflict (code) do update
  set name     = excluded.name,
      category = excluded.category,
      hint     = excluded.hint,
      aliases  = excluded.aliases;

-- ---------------------------------------------------------------------------
-- display_names -- what each skill is called in the person's own language.
-- Applied as a second pass so the taxonomy insert above stays readable.
-- ---------------------------------------------------------------------------
with labels (code, names) as (values
  ('SK001', '{"ta": "இருசக்கர வாகன பழுது நீக்கம்", "hi": "दोपहिया मरम्मत"}'),
  ('SK002', '{"ta": "கார் பழுது நீக்கம்", "hi": "कार मरम्मत"}'),
  ('SK003', '{"ta": "கனரக வாகன பராமரிப்பு", "hi": "भारी वाहन रखरखाव"}'),
  ('SK014', '{"ta": "எஞ்சின் கோளாறு கண்டறிதல்", "hi": "इंजन जाँच"}'),
  ('SK015', '{"ta": "வாகன மின் வேலை", "hi": "वाहन बिजली का काम"}'),
  ('SK022', '{"ta": "வெல்டிங்", "hi": "वेल्डिंग"}'),
  ('SK023', '{"ta": "ஆர்க் வெல்டிங்", "hi": "आर्क वेल्डिंग"}'),
  ('SK024', '{"ta": "கேஸ் வெல்டிங்", "hi": "गैस वेल्डिंग"}'),
  ('SK025', '{"ta": "தகடு வேலை", "hi": "शीट मेटल का काम"}'),
  ('SK026', '{"ta": "லேத் வேலை", "hi": "लेथ मशीन का काम"}'),
  ('SK031', '{"ta": "மின் வயரிங்", "hi": "बिजली की वायरिंग"}'),
  ('SK032', '{"ta": "வீட்டு உபகரண பழுது", "hi": "उपकरण मरम्मत"}'),
  ('SK033', '{"ta": "ஏசி மற்றும் குளிர்சாதன பணி", "hi": "एसी और फ्रिज का काम"}'),
  ('SK041', '{"ta": "கொத்து வேலை", "hi": "राजमिस्त्री का काम"}'),
  ('SK042', '{"ta": "தச்சு வேலை", "hi": "बढ़ई का काम"}'),
  ('SK043', '{"ta": "கட்டட வர்ணம் பூசுதல்", "hi": "रंगाई-पुताई"}'),
  ('SK044', '{"ta": "குழாய் பணி", "hi": "प्लंबिंग"}'),
  ('SK045', '{"ta": "கம்பி வளைத்தல்", "hi": "सरिया बांधने का काम"}'),
  ('SK051', '{"ta": "தையல் வேலை", "hi": "सिलाई"}'),
  ('SK052', '{"ta": "எம்பிராய்டரி", "hi": "कढ़ाई"}'),
  ('SK053', '{"ta": "விசைத்தறி இயக்குதல்", "hi": "पावरलूम चलाना"}'),
  ('SK054', '{"ta": "தறி இயந்திர பராமரிப்பு", "hi": "लूम मशीन रखरखाव"}'),
  ('SK061', '{"ta": "சமையல் வேலை", "hi": "रसोई का काम"}'),
  ('SK062', '{"ta": "பேக்கரி வேலை", "hi": "बेकरी का काम"}'),
  ('SK063', '{"ta": "சுத்தம் செய்யும் பணி", "hi": "साफ़-सफ़ाई का काम"}'),
  ('SK071', '{"ta": "விவசாயம்", "hi": "खेती"}'),
  ('SK072', '{"ta": "கால்நடை வளர்ப்பு", "hi": "पशुपालन"}'),
  ('SK073', '{"ta": "கோழி வளர்ப்பு", "hi": "मुर्गी पालन"}'),
  ('SK074', '{"ta": "பண்ணை இயந்திர இயக்கம்", "hi": "खेती की मशीन चलाना"}'),
  ('SK081', '{"ta": "லேசான வாகனம் ஓட்டுதல்", "hi": "हल्का वाहन चलाना"}'),
  ('SK082', '{"ta": "கனரக வாகனம் ஓட்டுதல்", "hi": "भारी वाहन चलाना"}'),
  ('SK083', '{"ta": "சுமை ஏற்றி இறக்குதல்", "hi": "लोडिंग-अनलोडिंग"}'),
  ('SK091', '{"ta": "கடை விற்பனை", "hi": "दुकान की बिक्री"}'),
  ('SK092', '{"ta": "கடை கணக்கு வேலை", "hi": "दुकान का हिसाब"}'),
  ('SK093', '{"ta": "சரக்கு பராமரிப்பு", "hi": "स्टॉक संभालना"}'),
  ('SK094', '{"ta": "சொந்த தொழில் நடத்துதல்", "hi": "अपना काम चलाना"}'),
  ('SK101', '{"ta": "மொபைல் போன் பழுது", "hi": "मोबाइल मरम्मत"}'),
  ('SK102', '{"ta": "கம்ப்யூட்டர் பழுது", "hi": "कंप्यूटर मरम्मत"}'),
  ('SK103', '{"ta": "கம்ப்யூட்டர் பயன்பாடு", "hi": "कंप्यूटर चलाना"}'),
  ('SK108', '{"ta": "வாடிக்கையாளர் கையாளுதல்", "hi": "ग्राहक व्यवहार"}'),
  ('SK109', '{"ta": "குழு மேற்பார்வை", "hi": "टीम की देखरेख"}'),
  ('SK110', '{"ta": "பாதுகாப்புப் பணி", "hi": "सुरक्षा का काम"}'),
  ('SK111', '{"ta": "அழகுக் கலை", "hi": "ब्यूटी का काम"}'),
  ('SK112', '{"ta": "மருத்துவ உதவிப் பணி", "hi": "मरीज़ की देखभाल"}')
)
update skill_taxonomy t
   set display_names = jsonb_build_object('en', t.name) || l.names::jsonb
  from labels l
 where t.code = l.code;

-- ---------------------------------------------------------------------------
-- schemes
-- Salem / Erode district (Tamil Nadu) worked example. source_reference points
-- back at the OGD / scheme record the row was derived from.
-- ---------------------------------------------------------------------------
insert into schemes (
  title, organization, location, district, type, minimum_experience,
  certifications_required, salary_min, salary_max, nsqf_level,
  source_reference, description
) values
  ('Two-Wheeler Service Technician', 'Ratnam Auto Works', 'Salem', 'Salem',
   'Full-time', 2, '[]'::jsonb, 14000, 18000, '4',
   'OGD/TN/SLM/AUTO/2024/0117',
   'Servicing and repair of motorcycles and scooters at a workshop in Salem town. Two years of hands-on repair experience expected. No formal certificate required -- the workshop trains on the job. Six-day week.'),

  ('Advanced Two-Wheeler Mechanic Training', 'Government ITI Salem', 'Salem', 'Salem',
   'Training', 0, '[]'::jsonb, 3000, 3000, '4',
   'PMAJAY/SKILL/TN/SLM/ITI/2024/0042',
   'Four-month certificate course in advanced two-wheeler mechanics. Monthly stipend of Rs 3,000. No course fee for SC candidates under PM-AJAY. Certificate is NSQF Level 4 aligned.'),

  ('Own Workshop Setup Support', 'PM-AJAY Livelihood Cell', 'Salem', 'Salem',
   'Self-employment support', 3, '[]'::jsonb, null, 200000, null,
   'PMAJAY/LIV/TN/SLM/2024/0008',
   'Capital support of up to Rs 2,00,000 for setting up an independent repair workshop. Applicants should have practical trade experience and some exposure to running a shop. Support is disbursed in two tranches against a simple business plan.'),

  ('Light Motor Vehicle Assistant', 'Kongu Transport', 'Erode', 'Erode',
   'Full-time', 1, '[]'::jsonb, 12000, 15000, '3',
   'OGD/TN/ERD/TRANS/2024/0233',
   'Assisting with maintenance and running repairs on a light commercial vehicle fleet in Erode. Mechanical aptitude expected; heavy vehicle experience is not required.'),

  ('Auto Electrician', 'Sri Balaji Motors', 'Salem', 'Salem',
   'Full-time', 2, '[]'::jsonb, 15000, 20000, '4',
   'OGD/TN/SLM/AUTO/2024/0189',
   'Vehicle electrical work -- wiring, battery, lighting and starter systems -- for two and four wheelers. Prior workshop experience expected.'),

  ('Welder (Fabrication Unit)', 'Annai Steel Fabricators', 'Salem', 'Salem',
   'Full-time', 1, '[]'::jsonb, 16000, 21000, '4',
   'OGD/TN/SLM/FAB/2024/0074',
   'Arc and gas welding on gates, grills and structural frames. Fabrication unit on the Salem-Attur road. Safety gear provided.'),

  ('Welding Certification Course (NSQF 4)', 'Government ITI Salem', 'Salem', 'Salem',
   'Training', 0, '[]'::jsonb, 2500, 2500, '4',
   'PMAJAY/SKILL/TN/SLM/ITI/2024/0051',
   'Three-month welding certificate course with a monthly stipend of Rs 2,500. Fee waived for SC candidates under PM-AJAY.'),

  ('Retail Counter Assistant', 'Sakthi Spare Parts', 'Salem', 'Salem',
   'Full-time', 0, '[]'::jsonb, 11000, 13000, '3',
   'OGD/TN/SLM/RET/2024/0311',
   'Counter sales of automobile spare parts. Involves handling customers and keeping stock records. Familiarity with vehicle parts is an advantage.'),

  ('Machine Operator (Power Loom)', 'Erode Textile Mills', 'Erode', 'Erode',
   'Full-time', 1, '[]'::jsonb, 13000, 16000, '3',
   'OGD/TN/ERD/TEX/2024/0402',
   'Operating and minding power looms on a shift basis. Training provided for the first month.'),

  ('Loom Maintenance Technician', 'Erode Textile Mills', 'Erode', 'Erode',
   'Full-time', 2, '[]'::jsonb, 15000, 19000, '4',
   'OGD/TN/ERD/TEX/2024/0403',
   'Keeping power looms and spinning machines running. Mechanical repair background expected; loom-specific training is given on site.'),

  ('Electrician (Building Sites)', 'Vetri Constructions', 'Salem', 'Salem',
   'Full-time', 2, '[]'::jsonb, 15000, 19000, '4',
   'OGD/TN/SLM/CON/2024/0155',
   'House and commercial wiring on residential sites across Salem district.'),

  ('Tailoring Unit Support', 'PM-AJAY Livelihood Cell', 'Salem', 'Salem',
   'Self-employment support', 1, '[]'::jsonb, null, 100000, null,
   'PMAJAY/LIV/TN/SLM/2024/0011',
   'Capital support of up to Rs 1,00,000 for setting up a tailoring unit, including machine purchase. Basic stitching experience expected.'),

  ('Mobile Phone Repair Training', 'District Skill Centre', 'Salem', 'Salem',
   'Training', 0, '[]'::jsonb, 2000, 2000, '3',
   'PMAJAY/SKILL/TN/SLM/DSC/2024/0027',
   'Two-month course in mobile phone repair with a monthly stipend of Rs 2,000. Includes screen, battery and basic board-level work.'),

  ('Driver (Light Commercial Vehicle)', 'Kongu Transport', 'Erode', 'Erode',
   'Full-time', 2, '["LMV Driving Licence"]'::jsonb, 14000, 17000, '3',
   'OGD/TN/ERD/TRANS/2024/0240',
   'Driving a light goods vehicle on district routes. A valid LMV licence is required.'),

  ('Dairy Unit Support', 'PM-AJAY Livelihood Cell', 'Attur', 'Salem',
   'Self-employment support', 1, '[]'::jsonb, null, 150000, null,
   'PMAJAY/LIV/TN/SLM/2024/0019',
   'Capital support of up to Rs 1,50,000 towards cattle purchase and shed construction for a small dairy unit.'),

  ('Housekeeping Supervisor', 'Salem Multispeciality Hospital', 'Salem', 'Salem',
   'Full-time', 3, '[]'::jsonb, 14000, 17000, '4',
   'OGD/TN/SLM/HLT/2024/0088',
   'Supervising a housekeeping team across hospital wards. Experience of leading a small crew is expected.')
on conflict do nothing;

-- ---------------------------------------------------------------------------
-- scheme_skills
-- Joined by natural keys so the block is re-runnable and readable.
-- ---------------------------------------------------------------------------
with wanted (source_reference, skill_code, weight, is_essential) as (values
  -- Two-Wheeler Service Technician
  ('OGD/TN/SLM/AUTO/2024/0117', 'SK001', 1.00, true),
  ('OGD/TN/SLM/AUTO/2024/0117', 'SK014', 0.80, true),
  ('OGD/TN/SLM/AUTO/2024/0117', 'SK108', 0.40, false),
  -- Advanced Two-Wheeler Mechanic Training
  ('PMAJAY/SKILL/TN/SLM/ITI/2024/0042', 'SK001', 1.00, true),
  ('PMAJAY/SKILL/TN/SLM/ITI/2024/0042', 'SK014', 0.70, false),
  -- Own Workshop Setup Support
  ('PMAJAY/LIV/TN/SLM/2024/0008', 'SK001', 0.80, true),
  ('PMAJAY/LIV/TN/SLM/2024/0008', 'SK094', 0.90, true),
  ('PMAJAY/LIV/TN/SLM/2024/0008', 'SK108', 0.60, false),
  -- Light Motor Vehicle Assistant
  ('OGD/TN/ERD/TRANS/2024/0233', 'SK002', 0.90, true),
  ('OGD/TN/ERD/TRANS/2024/0233', 'SK014', 0.80, true),
  -- Auto Electrician
  ('OGD/TN/SLM/AUTO/2024/0189', 'SK015', 1.00, true),
  ('OGD/TN/SLM/AUTO/2024/0189', 'SK014', 0.60, false),
  ('OGD/TN/SLM/AUTO/2024/0189', 'SK001', 0.50, false),
  -- Welder (Fabrication Unit)
  ('OGD/TN/SLM/FAB/2024/0074', 'SK023', 1.00, true),
  ('OGD/TN/SLM/FAB/2024/0074', 'SK024', 0.80, false),
  ('OGD/TN/SLM/FAB/2024/0074', 'SK025', 0.60, false),
  -- Welding Certification Course
  ('PMAJAY/SKILL/TN/SLM/ITI/2024/0051', 'SK022', 1.00, true),
  -- Retail Counter Assistant
  ('OGD/TN/SLM/RET/2024/0311', 'SK091', 1.00, true),
  ('OGD/TN/SLM/RET/2024/0311', 'SK108', 0.80, true),
  ('OGD/TN/SLM/RET/2024/0311', 'SK093', 0.60, false),
  -- Machine Operator (Power Loom)
  ('OGD/TN/ERD/TEX/2024/0402', 'SK053', 1.00, true),
  -- Loom Maintenance Technician
  ('OGD/TN/ERD/TEX/2024/0403', 'SK054', 1.00, true),
  ('OGD/TN/ERD/TEX/2024/0403', 'SK026', 0.50, false),
  -- Electrician (Building Sites)
  ('OGD/TN/SLM/CON/2024/0155', 'SK031', 1.00, true),
  -- Tailoring Unit Support
  ('PMAJAY/LIV/TN/SLM/2024/0011', 'SK051', 1.00, true),
  ('PMAJAY/LIV/TN/SLM/2024/0011', 'SK094', 0.70, false),
  -- Mobile Phone Repair Training
  ('PMAJAY/SKILL/TN/SLM/DSC/2024/0027', 'SK101', 1.00, true),
  -- Driver (LCV)
  ('OGD/TN/ERD/TRANS/2024/0240', 'SK081', 1.00, true),
  -- Dairy Unit Support
  ('PMAJAY/LIV/TN/SLM/2024/0019', 'SK072', 1.00, true),
  ('PMAJAY/LIV/TN/SLM/2024/0019', 'SK094', 0.60, false),
  -- Housekeeping Supervisor
  ('OGD/TN/SLM/HLT/2024/0088', 'SK063', 1.00, true),
  ('OGD/TN/SLM/HLT/2024/0088', 'SK109', 0.80, true)
)
insert into scheme_skills (scheme_id, skill_id, weight, is_essential)
select o.id, t.id, w.weight::numeric(3,2), w.is_essential
from wanted w
join schemes o on o.source_reference = w.source_reference
join skill_taxonomy t on t.code = w.skill_code
on conflict (scheme_id, skill_id) do update
  set weight = excluded.weight,
      is_essential = excluded.is_essential;
