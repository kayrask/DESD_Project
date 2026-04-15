"""
Usage:
    python manage.py seed_db

Creates the demo users, products, orders, and commission reports used in
sprint demos. Safe to run multiple times — existing records are skipped.
"""

from django.core.management.base import BaseCommand

from api.models import CommissionReport, Order, Product, User


class Command(BaseCommand):
    help = "Seed the database with demo data for sprint demonstrations"

    def handle(self, *args, **options):
        self.stdout.write("Seeding database...")

        # ── Django superuser (for /admin/ panel) ─────────────────────────────
        if not User.objects.filter(email="superadmin@desd.local").exists():
            User.objects.create_superuser(
                email="superadmin@desd.local",
                password="Admin1234",
                full_name="Super Admin",
                role="admin",
            )
            self.stdout.write("  created superuser: superadmin@desd.local / Admin1234")
        else:
            self.stdout.write("  skip superuser: superadmin@desd.local")

        # ── Users ────────────────────────────────────────────────────────────
        producer = self._get_or_create_user(
            email="producer@desd.local",
            password="Password123",
            role="producer",
            full_name="Green Valley Farm",
        )
        producer2 = self._get_or_create_user(
            email="producer2@desd.local",
            password="Password123",
            role="producer",
            full_name="Hillside Organic Co.",
        )
        self._get_or_create_user(
            email="admin@desd.local",
            password="Password123",
            role="admin",
            full_name="Admin User",
        )
        self._get_or_create_user(
            email="customer@desd.local",
            password="Password123",
            role="customer",
            full_name="Customer User",
        )
        self._get_or_create_user(
            email="suspended@desd.local",
            password="Password123",
            role="customer",
            full_name="Suspended User",
            status="suspended",
        )

        # ── Products — Green Valley Farm ─────────────────────────────────────
        self._get_or_create_product(
            producer=producer,
            name="Heirloom Tomatoes",
            category="Vegetable",
            description=(
                "Grown from century-old seed varieties passed down through generations. "
                "These deep-red, irregularly shaped tomatoes are rich in umami flavour "
                "and far superior to supermarket counterparts. Best eaten raw in salads "
                "or sliced with good olive oil and sea salt. Picked same-day for maximum freshness."
            ),
            price=4.50,
            stock=52,
            status="In Season",
        )
        self._get_or_create_product(
            producer=producer,
            name="Winter Kale",
            category="Leafy Greens",
            description=(
                "Hardy curly kale harvested after the first frost, which converts starches "
                "to sugar and significantly sweetens the leaves. High in vitamins K, A, and C. "
                "Excellent raw in massaged salads, sautéed with garlic, or blended into smoothies. "
                "Supplied in 250 g bunches."
            ),
            price=3.20,
            stock=0,
            status="Out of Stock",
        )
        self._get_or_create_product(
            producer=producer,
            name="Organic Carrots",
            category="Vegetable",
            description=(
                "Unwashed Chantenay carrots grown in deep, stone-free loam soil without "
                "synthetic pesticides or fertilisers. Their short, stout shape concentrates "
                "natural sweetness. Perfect for roasting, juicing, or eating raw as a snack. "
                "Sold in 500 g bunches with tops attached."
            ),
            price=2.80,
            stock=34,
            status="Available",
            is_organic=True,
        )
        self._get_or_create_product(
            producer=producer,
            name="Free-Range Eggs (dozen)",
            category="Dairy & Eggs",
            description=(
                "Mixed-size eggs from hens with year-round outdoor access to grass pasture. "
                "Fed a non-GM grain diet supplemented with insects and greens they forage "
                "themselves. Deep-orange yolks, rich flavour, and noticeably firmer whites "
                "compared to caged alternatives. Collected and packed daily."
            ),
            price=3.90,
            stock=20,
            status="Available",
            allergens="Eggs",
        )
        self._get_or_create_product(
            producer=producer,
            name="Baby Spinach",
            category="Leafy Greens",
            description=(
                "Tender young spinach leaves harvested before full maturity for a mild, "
                "slightly sweet flavour without the metallic edge of mature spinach. "
                "Triple-washed and ready to eat straight from the bag. High in iron, "
                "folate, and antioxidants. Use in salads, smoothies, or wilt into pasta "
                "and omelettes. Sold in 100 g bags."
            ),
            price=2.50,
            stock=45,
            status="In Season",
        )
        self._get_or_create_product(
            producer=producer,
            name="Butternut Squash",
            category="Vegetable",
            description=(
                "Cured for two weeks after harvest to develop sweetness and extend shelf life. "
                "Dense, vibrant orange flesh with a nutty, buttery flavour that deepens when "
                "roasted. One squash typically weighs 900 g–1.2 kg and serves four as a side. "
                "Excellent in soups, risottos, curries, or simply halved and roasted with honey."
            ),
            price=3.10,
            stock=28,
            status="Available",
        )
        self._get_or_create_product(
            producer=producer,
            name="Leeks",
            category="Vegetable",
            description=(
                "Long, white-shanked leeks grown slowly over winter for a mild, sweet onion "
                "flavour. Ideal for soups, gratins, quiches, and stir-fries. Supplied in "
                "bundles of three, each approximately 30 cm long. Wash thoroughly before use "
                "as soil naturally accumulates between the layers."
            ),
            price=2.20,
            stock=60,
            status="Available",
        )
        self._get_or_create_product(
            producer=producer,
            name="Courgettes",
            category="Vegetable",
            description=(
                "Harvested young at 15–18 cm when the flesh is most tender and seeds minimal. "
                "Versatile and delicate — spiralise raw into 'zoodles', griddle as a starter, "
                "fold into fritters, or slice into a summer tart. Supplied in packs of four. "
                "Best consumed within five days of delivery."
            ),
            price=2.00,
            stock=38,
            status="Available",
        )
        self._get_or_create_product(
            producer=producer,
            name="Mixed Salad Leaves",
            category="Leafy Greens",
            description=(
                "A hand-blended mix of rocket, red oak leaf, lollo rosso, lamb's lettuce, "
                "and mustard greens. Harvested early morning and packed within two hours "
                "to lock in crispness. Peppery, slightly bitter, and complex — this is a "
                "restaurant-quality salad base. Supplied in 120 g bags. No pre-washing needed."
            ),
            price=3.00,
            stock=50,
            status="Available",
        )
        self._get_or_create_product(
            producer=producer,
            name="Red Onions",
            category="Vegetable",
            description=(
                "Medium-sized red onions with a vivid purple skin and crisp, mildly pungent "
                "flesh. The relatively low pungency makes them ideal raw in salads, pickled "
                "in vinegar, or caramelised low and slow until jammy and sweet. Sold in "
                "nets of six (approximately 800 g). Store in a cool, dry place for up to three weeks."
            ),
            price=1.80,
            stock=75,
            status="Available",
        )
        self._get_or_create_product(
            producer=producer,
            name="Fresh Garlic Bulbs",
            category="Herb & Spice",
            description=(
                "Freshly lifted hardneck garlic with plump cloves and papery white skins. "
                "Far more aromatic than dried garlic — the volatile sulphur compounds "
                "haven't had time to dissipate. Each bulb contains 8–12 cloves. "
                "Excellent roasted whole, crushed into dressings, or used as the "
                "flavour backbone of virtually any savoury dish. Sold in packs of three bulbs."
            ),
            price=2.40,
            stock=40,
            status="Available",
        )
        self._get_or_create_product(
            producer=producer,
            name="Chestnut Mushrooms",
            category="Mushroom",
            description=(
                "Firm, brown-capped chestnut mushrooms grown on composted straw in "
                "our humidity-controlled growing room. A step up from white button mushrooms "
                "in both texture and depth of flavour — earthy, slightly nutty, and "
                "satisfying. Great in risottos, pan sauces, full English breakfasts, or "
                "skewered on the barbecue. Sold in 300 g punnets."
            ),
            price=2.60,
            stock=35,
            status="Available",
        )
        self._get_or_create_product(
            producer=producer,
            name="Oyster Mushrooms",
            category="Mushroom",
            description=(
                "Delicate, fan-shaped oyster mushrooms with a silky texture and mild, "
                "slightly oceanic flavour that becomes richer when cooked. Because they "
                "absorb fat beautifully, a simple butter-and-thyme pan-fry is enough to "
                "make them shine. Also excellent in Asian broths and vegan stir-fries. "
                "Sold in 200 g clusters, best used within three days."
            ),
            price=3.50,
            stock=22,
            status="Available",
        )
        self._get_or_create_product(
            producer=producer,
            name="Wildflower Honey (340 g)",
            category="Honey & Preserves",
            description=(
                "Raw, unpasteurised honey from hives placed among wildflower meadows "
                "across our farm. Cold-extracted and unheated to preserve natural enzymes, "
                "pollen, and antioxidants destroyed by commercial processing. "
                "Flavour changes subtly with the seasons — early summer is floral and "
                "light; late summer develops a deeper, more complex amber character. "
                "May crystallise naturally — this is a sign of quality, not spoilage."
            ),
            price=7.50,
            stock=18,
            status="Available",
        )
        self._get_or_create_product(
            producer=producer,
            name="Strawberry Jam (320 g)",
            category="Honey & Preserves",
            description=(
                "Made in small batches using only our own field-grown strawberries and "
                "unrefined cane sugar — no pectin, no preservatives, no concentrates. "
                "Cooked briefly to retain bright fruit flavour rather than a heavy, "
                "over-boiled taste. A high fruit-to-sugar ratio (60:40) gives a fresher, "
                "less sweet result than commercial jams. Sealed in glass jars for a shelf "
                "life of 12 months unopened."
            ),
            price=5.20,
            stock=14,
            status="Available",
        )

        # ── Products — Hillside Organic Co. ──────────────────────────────────
        self._get_or_create_product(
            producer=producer2,
            name="Cox Apples",
            category="Fruit",
            description=(
                "A classic British eating apple with a complex, spiced aroma and a "
                "crisp, juicy bite that balances sweetness with a refreshing acidity. "
                "Cox's Orange Pippin is widely regarded as the finest eating apple "
                "grown in the UK. These are picked by hand at peak ripeness and stored "
                "in our cool barn — not in controlled-atmosphere cold storage. "
                "Sold in bags of six, approximately 700 g."
            ),
            price=3.80,
            stock=60,
            status="Available",
            is_organic=True,
        )
        self._get_or_create_product(
            producer=producer2,
            name="Conference Pears",
            category="Fruit",
            description=(
                "Long, elegant pears with russeted green-yellow skin and smooth, "
                "honey-sweet flesh with very little grittiness. Best eaten when the "
                "neck just begins to yield to gentle pressure — fully ripe but not "
                "overripe. Excellent with strong cheese, poached in red wine, or "
                "simply eaten out of hand. Sold in bags of four."
            ),
            price=3.40,
            stock=44,
            status="Available",
            is_organic=True,
        )
        self._get_or_create_product(
            producer=producer2,
            name="Raspberries (125 g)",
            category="Fruit",
            description=(
                "Summer-fruiting Glen Ample raspberries known for their exceptional "
                "size and balance of sweetness and sharp berry tang. Grown without "
                "pesticides on cane trained along wires in our sheltered walled garden. "
                "Picked every two days to catch each berry at peak ripeness. "
                "Highly perishable — consume within two days of receipt. "
                "Sublime with cream, in pavlova, or stirred through morning porridge."
            ),
            price=3.20,
            stock=30,
            status="In Season",
            is_organic=True,
        )
        self._get_or_create_product(
            producer=producer2,
            name="Blueberries (150 g)",
            category="Fruit",
            description=(
                "Plump Duke and Bluecrop variety blueberries with a dusty blue-grey "
                "bloom indicating freshness. Grown on acidic, ericaceous soil that "
                "is naturally free-draining. Rich in anthocyanins and vitamin C. "
                "Flavour is a clean sweet-tart balance — noticeably more complex "
                "than imported berries. Excellent in baking, on yoghurt, or eaten "
                "by the handful as a snack."
            ),
            price=3.60,
            stock=26,
            status="In Season",
            is_organic=True,
        )
        self._get_or_create_product(
            producer=producer2,
            name="Raw Whole Milk (1 L)",
            category="Dairy & Eggs",
            description=(
                "Unpasteurised, unhomogenised whole milk from our grass-fed herd of "
                "Brown Swiss and Jersey crosses. The cream rises to the top — shake "
                "before use or spoon off for coffee. A noticeably richer, creamier "
                "flavour than any processed milk. Bottled in returnable glass. "
                "Keep refrigerated and consume within four days of collection. "
                "Suitable for making yoghurt, kefir, and soft cheeses at home."
            ),
            price=2.10,
            stock=40,
            status="Available",
            is_organic=True,
            allergens="Milk",
        )
        self._get_or_create_product(
            producer=producer2,
            name="Farmhouse Cheddar (200 g)",
            category="Dairy & Eggs",
            description=(
                "Cloth-bound, naturally rinded cheddar aged for a minimum of nine months "
                "in our stone dairy. Made exclusively from the milk of our own herd using "
                "traditional starter cultures and animal rennet. "
                "The texture is firm but crumbly, with a deep, complex flavour — "
                "savoury, slightly sharp, with a lingering finish. "
                "World-class on a cheeseboard, in a ploughman's, or melted on toast."
            ),
            price=6.80,
            stock=16,
            status="Available",
            is_organic=True,
            allergens="Milk",
        )
        self._get_or_create_product(
            producer=producer2,
            name="Natural Live Yoghurt (500 g)",
            category="Dairy & Eggs",
            description=(
                "Thick, whole-milk yoghurt set in the pot using live cultures — "
                "Lactobacillus bulgaricus and Streptococcus thermophilus — which remain "
                "active up to the best-before date. Pleasantly tart with a clean, "
                "fresh dairy flavour. No thickeners, stabilisers, or added sugar. "
                "Excellent with granola and fruit, as a marinade base, or as a substitute "
                "for soured cream in dips and dressings."
            ),
            price=2.90,
            stock=32,
            status="Available",
            is_organic=True,
            allergens="Milk",
        )
        self._get_or_create_product(
            producer=producer2,
            name="Portobello Mushrooms",
            category="Mushroom",
            description=(
                "Large, open-capped portobello mushrooms with a diameter of 10–14 cm. "
                "The wide, dark-gilled cap has a dense, meaty texture that holds its "
                "structure when grilled or roasted — making it the definitive burger "
                "substitute or a spectacular centrepiece stuffed with garlic butter, "
                "breadcrumbs, and herbs. Each pack contains two caps."
            ),
            price=2.80,
            stock=24,
            status="Available",
            is_organic=True,
        )
        self._get_or_create_product(
            producer=producer2,
            name="Stone-Ground Wholemeal Flour (1 kg)",
            category="Grain & Pulses",
            description=(
                "Milled on a traditional granite millstone from heritage Maris Widgeon "
                "wheat grown on our farm. Stone-grinding keeps the bran, germ, and "
                "endosperm intact and generates less heat than roller milling, "
                "preserving delicate flavour compounds and nutrients. "
                "Produces a more complex, slightly nutty loaf than supermarket wholemeal. "
                "Ideal for sourdough, soda bread, and pastry."
            ),
            price=3.20,
            stock=50,
            status="Available",
            is_organic=True,
            allergens="Gluten, Wheat",
        )
        self._get_or_create_product(
            producer=producer2,
            name="Rolled Oats (750 g)",
            category="Grain & Pulses",
            description=(
                "Large-flake oats made from whole organic oat groats, steam-treated and "
                "rolled to roughly 1 mm thickness. The larger flake size means slower "
                "digestion and a lower glycaemic impact than instant oats, as well as a "
                "creamier, more satisfying porridge with genuine texture. "
                "Also excellent in overnight oats, granola, flapjacks, and crumble toppings."
            ),
            price=2.40,
            stock=55,
            status="Available",
            is_organic=True,
            allergens="Gluten (Oats)",
        )
        self._get_or_create_product(
            producer=producer2,
            name="Green Lentils (500 g)",
            category="Grain & Pulses",
            description=(
                "Puy-style green lentils grown in our market garden and sun-dried. "
                "Unlike red split lentils, these hold their shape when cooked, making "
                "them ideal for warm salads, side dishes, and hearty soups where texture "
                "matters. Rich in plant protein (25 g per 100 g) and soluble fibre. "
                "No soaking required — cook in 25–30 minutes. Supplied in resealable bags."
            ),
            price=2.80,
            stock=42,
            status="Available",
            is_organic=True,
        )
        self._get_or_create_product(
            producer=producer2,
            name="Fresh Thyme (30 g)",
            category="Herb & Spice",
            description=(
                "Woody-stemmed fresh thyme cut on the morning of dispatch. "
                "Intensely aromatic with a complex flavour profile — earthy, floral, "
                "and faintly lemony — that holds up well during long cooking. "
                "Essential in stocks, braises, roast chicken, and Mediterranean dishes. "
                "Strip the leaves from the stem or add whole sprigs and remove before serving. "
                "Keep wrapped in damp paper in the fridge for up to one week."
            ),
            price=1.60,
            stock=48,
            status="In Season",
            is_organic=True,
        )
        self._get_or_create_product(
            producer=producer2,
            name="Fresh Rosemary (30 g)",
            category="Herb & Spice",
            description=(
                "Robust, resinous rosemary sprigs cut from established bushes — "
                "older plants produce more intensely fragrant oil than young nursery herbs. "
                "The piney, camphoraceous aroma is extraordinary alongside lamb, potatoes, "
                "focaccia, and marinades. Use sparingly — a little goes a long way. "
                "Also wonderful infused into olive oil or butter. "
                "Keeps well in the fridge for 10–14 days."
            ),
            price=1.60,
            stock=44,
            status="Available",
            is_organic=True,
        )
        self._get_or_create_product(
            producer=producer2,
            name="Dried Chilli Flakes (50 g)",
            category="Herb & Spice",
            description=(
                "Dried and crushed from our own Calabrian and bird's eye chilli varieties. "
                "Medium-hot with a moderate 15,000–30,000 Scoville rating — enough "
                "warmth to notice but not overwhelm. A complex, slightly smoky fruitiness "
                "underpins the heat, something absent in generic supermarket flakes. "
                "Use to finish pizza, pasta, eggs, and stir-fries. "
                "Supplied in a resealable amber glass jar to protect against light degradation."
            ),
            price=2.20,
            stock=36,
            status="Available",
            is_organic=True,
        )
        self._get_or_create_product(
            producer=producer2,
            name="Apple Cider Vinegar (500 ml)",
            category="Honey & Preserves",
            description=(
                "Unpasteurised, unfiltered cider vinegar made from pressed Cox and Bramley "
                "apples from our orchard. Fermented for six weeks then aged in oak for "
                "a further three months. The cloudy sediment — the 'mother of vinegar' — "
                "contains beneficial bacteria and enzymes. "
                "Use in salad dressings, marinades, shrubs, and pickling. "
                "Many customers also take a teaspoon diluted in water as a daily tonic."
            ),
            price=4.50,
            stock=20,
            status="Available",
            is_organic=True,
        )
        self._get_or_create_product(
            producer=producer2,
            name="Plum Chutney (290 g)",
            category="Honey & Preserves",
            description=(
                "Slow-cooked in copper pans from Victoria plums, red onion, dark sugar, "
                "cider vinegar, and a house spice blend that includes clove, star anise, "
                "and ginger. The result is a deeply complex, sweet-sour condiment "
                "that pairs brilliantly with mature cheeses, cold cuts, pork pies, "
                "and game. Made in batches of 60 jars — each jar is individually labelled "
                "with the batch number and date. Minimum two months' mellowing before sale."
            ),
            price=4.80,
            stock=12,
            status="Available",
            is_organic=True,
        )

        # ── Orders ───────────────────────────────────────────────────────────
        self._get_or_create_order(
            producer=producer,
            order_id="D-1023",
            customer_name="John Smith",
            delivery_date="2026-03-06",
            status="Pending",
        )
        self._get_or_create_order(
            producer=producer,
            order_id="D-1019",
            customer_name="Jane Doe",
            delivery_date="2026-03-05",
            status="Confirmed",
        )
        self._get_or_create_order(
            producer=producer,
            order_id="D-1031",
            customer_name="Alice Brown",
            delivery_date="2026-03-10",
            status="Pending",
        )
        self._get_or_create_order(
            producer=producer2,
            order_id="D-2011",
            customer_name="Oliver Green",
            delivery_date="2026-03-08",
            status="Ready",
        )
        self._get_or_create_order(
            producer=producer2,
            order_id="D-2017",
            customer_name="Sophie Turner",
            delivery_date="2026-03-12",
            status="Pending",
        )

        # ── Commission Reports ────────────────────────────────────────────────
        self._get_or_create_report("2026-03-01", 24, 4820.00, 241.00)
        self._get_or_create_report("2026-02-28", 19, 3110.00, 155.50)
        self._get_or_create_report("2026-02-21", 22, 4100.00, 205.00)

        self.stdout.write(self.style.SUCCESS("Database seeded successfully."))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_or_create_user(self, email, password, role, full_name, status="active"):
        if User.objects.filter(email=email).exists():
            self.stdout.write(f"  skip user: {email}")
            return User.objects.get(email=email)
        user = User.objects.create_user(
            email=email,
            password=password,
            role=role,
            full_name=full_name,
            status=status,
        )
        self.stdout.write(f"  created user: {email}")
        return user

    def _get_or_create_product(self, producer, name, category, description, price, stock, status,
                               allergens="", is_organic=False):
        obj, created = Product.objects.get_or_create(
            name=name,
            producer=producer,
            defaults={
                "category": category,
                "description": description,
                "price": price,
                "stock": stock,
                "status": status,
                "allergens": allergens,
                "is_organic": is_organic,
            },
        )
        if not created:
            update_fields = []
            if obj.description != description:
                obj.description = description
                update_fields.append("description")
            if obj.allergens != allergens:
                obj.allergens = allergens
                update_fields.append("allergens")
            if obj.is_organic != is_organic:
                obj.is_organic = is_organic
                update_fields.append("is_organic")
            if obj.status != status:
                obj.status = status
                update_fields.append("status")
            if update_fields:
                obj.save(update_fields=update_fields)
        label = "created" if created else "skip"
        self.stdout.write(f"  {label} product: {name}")
        return obj

    def _get_or_create_order(self, producer, order_id, customer_name, delivery_date, status):
        obj, created = Order.objects.get_or_create(
            order_id=order_id,
            defaults={
                "producer": producer,
                "customer_name": customer_name,
                "delivery_date": delivery_date,
                "status": status,
            },
        )
        label = "created" if created else "skip"
        self.stdout.write(f"  {label} order: {order_id}")
        return obj

    def _get_or_create_report(self, report_date, total_orders, gross, commission):
        obj, created = CommissionReport.objects.get_or_create(
            report_date=report_date,
            defaults={
                "total_orders": total_orders,
                "gross_amount": gross,
                "commission_amount": commission,
            },
        )
        if created:
            self.stdout.write(f"  created report: {report_date}")
            return obj

        changed = False
        if obj.total_orders != total_orders:
            obj.total_orders = total_orders
            changed = True
        if float(obj.gross_amount) != float(gross):
            obj.gross_amount = gross
            changed = True
        if float(obj.commission_amount) != float(commission):
            obj.commission_amount = commission
            changed = True
        if changed:
            obj.save()
            self.stdout.write(f"  updated report: {report_date}")
        else:
            self.stdout.write(f"  skip report: {report_date}")
        return obj
