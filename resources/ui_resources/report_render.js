/**
 * 观影报告渲染核心逻辑 (Optimized)
 * 结构：单例模式 ReportApp
 * 包含：Constants, Utils, Templates, Charts, Features, Init
 */

const ReportApp = (() => {
    // ================= Part 1: 常量与映射 =================
    const Constants = {
        COUNTRY_MAP: {
            '中国': 'China', '中国大陆': 'China', '韩国': 'Korea', '中国香港': 'Hong Kong',
            '中国台湾': 'Taiwan', '美国': 'United States', '英国': 'United Kingdom',
            '法国': 'France', '德国': 'Germany', '意大利': 'Italy', '西班牙': 'Spain',
            '日本': 'Japan', '南韩': 'South Korea', '印度': 'India', '俄罗斯': 'Russia',
            '加拿大': 'Canada', '澳大利亚': 'Australia', '墨西哥': 'Mexico', '巴西': 'Brazil',
            '阿根廷': 'Argentina', '瑞典': 'Sweden', '挪威': 'Norway', '丹麦': 'Denmark',
            '芬兰': 'Finland', '波兰': 'Poland', '捷克': 'Czech Republic', '荷兰': 'Netherlands',
            '比利时': 'Belgium', '瑞士': 'Switzerland', '奥地利': 'Austria', '爱尔兰': 'Ireland',
            '新西兰': 'New Zealand', '泰国': 'Thailand', '越南': 'Vietnam', '新加坡': 'Singapore',
            '马来西亚': 'Malaysia', '印度尼西亚': 'Indonesia', '菲律宾': 'Philippines',
            '土耳其': 'Turkey', '伊朗': 'Iran', '以色列': 'Israel', '埃及': 'Egypt', '南非': 'South Africa'
        },
        // 导演映射表 (保持原数据，此处略去部分以节省空间，实际使用时请保留完整映射)
        DIRECTOR_MAP: window.DIRECTOR_MAP || {
            /* ... 原有的 DIRECTOR_MAP 内容 ... */
            /* 注意：为了保持代码整洁，假设原来的 DIRECTOR_MAP 定义在外部或此处应完整保留 */
            "Aamir Khan": "阿米尔·汗", "Christopher Nolan": "克里斯托弗·诺兰", "Hayao Miyazaki": "宫崎骏",
            // === A ===
            "Aamir Khan": "阿米尔·汗",
            "Aaron Russo": "亚伦·罗素",
            "Aaron Sorkin": "艾伦·索金",
            "Adam Elliot": "亚当·艾略特",
            "Adam McKay": "亚当·麦凯",
            "Adrian Molina": "阿德里安·莫利纳",
            "Aki Kaurismäki": "阿基·考里斯马基",
            "Alain Gsponer": "阿兰·葛斯彭纳",
            "Alain Resnais": "阿伦·雷奈",
            "Alan Gibson": "亚伦·吉布森",
            "Alan Parker": "艾伦·帕克",
            "Alejandro Amenábar": "亚历杭德罗·阿梅纳瓦尔",
            "Alejandro González Iñárritu": "亚历杭德罗·冈萨雷斯·伊尼亚里图",
            "Alejandro G. Iñárritu": "亚历杭德罗·冈萨雷斯·伊尼亚里图",
            "Alejandro Jodorowsky": "亚历杭德罗·佐杜洛夫斯基",
            "Alex Garland": "亚历克斯·加兰",
            "Alex Proyas": "亚历克斯·普罗亚斯",
            "Alexander Payne": "亚历山大·佩恩",
            "Alexander Witt": "亚历山大·维特",
            "Alfonso Cuarón": "阿方索·卡隆",
            "Alfred Hitchcock": "阿尔弗雷德·希区柯克",
            "Anand Tucker": "安南德·图克尔",
            "Andrés Baiz": "安德烈斯·拜",
            "Andrew Niccol": "安德鲁·尼科尔",
            "Andrew Stanton": "安德鲁·斯坦顿",
            "André Øvredal": "安德烈·欧弗兰多",
            "Ang Lee": "李安",
            "Anthony Mann": "安东尼·曼",
            "Anthony Russo": "安东尼·罗素",
            "Arthur Penn": "阿瑟·佩恩",
            "Asghar Farhadi": "阿斯哈·法哈蒂",

            // === B ===
            "Barry Levinson": "巴里·莱文森",
            "Barry Sonnenfeld": "巴里·索南菲尔德",
            "Baz Luhrmann": "巴兹·鲁赫曼",
            "Ben Stiller": "本·斯蒂勒",
            "Benjamin Renner": "本杰明·雷内",
            "Bernardo Bertolucci": "贝纳多·贝托鲁奇",
            "Billy Wilder": "比利·怀德",
            "Bob Fosse": "鲍勃·福斯",
            "Bob Peterson": "鲍勃·彼德森",
            "Bong Joon Ho": "奉俊昊",
            "Brad Bird": "布拉德·伯德",
            "Brett Ratner": "布莱特·拉特纳",
            "Brian De Palma": "布莱恩·德·帕尔玛",
            "Bryan Singer": "布莱恩·辛格",
            "Buster Keaton": "巴斯特·基顿",
            "Byron Howard": "拜伦·霍华德",

            // === C ===
            "Carlos Saldanha": "卡洛斯·沙尔丹哈",
            "Catherine Hardwicke": "凯瑟琳·哈德威克",
            "Chad Stahelski": "查德·斯塔赫斯基",
            "Charles Chaplin": "查理·卓别林",
            "Charlie Chaplin": "查理·卓别林",
            "Chris Buck": "克里斯·巴克",
            "Chris Columbus": "克里斯·哥伦布",
            "Chris Marker": "克里斯·马克",
            "Chris Renaud": "克里斯·雷纳德",
            "Chris Sanders": "克里斯·桑德斯",
            "Chris Wedge": "克里斯·韦奇",
            "Chris Williams": "克里斯·威廉姆斯",
            "Christian Petzold": "克里斯蒂安·佩措尔德",
            "Christopher Nolan": "克里斯托弗·诺兰",
            "Clint Eastwood": "克林特·伊斯特伍德",
            "Colin Trevorrow": "科林·特雷沃罗",
            "Coralie Fargeat": "科拉莉·法尔雅",
            "Craig Zobel": "克雷格·卓贝",
            "Curtis Hanson": "柯蒂斯·汉森",

            // === D ===
            "Damien Chazelle": "达米恩·查泽雷",
            "Damián Szifron": "达米安·斯兹弗隆",
            "Dan Kwan": "关家永",
            "Daniel Scheinert": "丹尼尔·施纳特",
            "Danny Boyle": "丹尼·博伊尔",
            "Darren Aronofsky": "达伦·阿伦诺夫斯基",
            "Darren Lynn Bousman": "达伦·林恩·鲍斯曼",
            "David Cronenberg": "大卫·柯南伯格",
            "David Fincher": "大卫·芬奇",
            "David Leitch": "大卫·雷奇",
            "David Lynch": "大卫·林奇",
            "David Yates": "大卫·叶茨",
            "Dean DeBlois": "迪恩·德布洛斯",
            "Denis Villeneuve": "丹尼斯·维伦纽瓦",
            "Dennis Gansel": "丹尼斯·甘塞尔",
            "Dennis Hopper": "丹尼斯·霍珀",
            "Don Hall": "唐·霍尔",
            "Doug Liman": "道格·里曼",
            "Drew Goddard": "德鲁·高达",
            "Duncan Jones": "邓肯·琼斯",

            // === E ===
            "Edgar Wright": "埃德加·赖特",
            "Edward Zwick": "爱德华·兹威克",
            "Elia Kazan": "伊利亚·卡赞",
            "Emma Tammi": "艾玛·坦米",
            "Eric Bress": "埃里克·布雷斯",
            "Eric Darnell": "埃里克·达尼尔",
            "Ethan Coen": "伊桑·科恩",
            "Ernst Lubitsch": "恩斯特·刘别谦",

            // === F ===
            "F. Gary Gray": "F·加里·格雷",
            "Federico Fellini": "费德里科·费里尼",
            "Fernando Meirelles": "费尔南多·梅里尔斯",
            "Florian Henckel von Donnersmarck": "弗洛里安·亨克尔·冯·多纳斯马马克",
            "Florian Zeller": "弗洛里安·泽勒",
            "Francis Ford Coppola": "弗朗西斯·福特·科波拉",
            "Francis Lawrence": "弗朗西斯·劳伦斯",
            "Frank Capra": "弗兰克·卡普拉",
            "Frank Darabont": "弗兰克·德拉邦特",
            "Franklin J. Schaffner": "富兰克林·J·沙夫纳",
            "François Ozon": "弗朗索瓦·欧容",
            "François Truffaut": "弗朗索瓦·特吕弗",
            "Fritz Lang": "弗里茨·朗",

            // === G ===
            "Gabriele Muccino": "加布里埃莱·穆奇诺",
            "Garth Jennings": "加斯·詹宁斯",
            "Gary Ross": "加里·罗斯",
            "George Miller": "乔治·米勒",
            "George Roy Hill": "乔治·罗伊·希尔",
            "Giuseppe Tornatore": "朱塞佩·托纳多雷",
            "Gore Verbinski": "戈尔·维宾斯基",
            "Greta Gerwig": "格蕾塔·葛韦格",
            "Guillermo del Toro": "吉尔莫·德尔·托罗",
            "Gus Van Sant": "格斯·范·桑特",
            "Guy Hamilton": "盖伊·汉弥尔顿",
            "Guy Ritchie": "盖·里奇",

            // === H ===
            "Hannes Holm": "汉内斯·赫尔姆",
            "Harold Ramis": "哈罗德·雷米斯",
            "Hayao Miyazaki": "宫崎骏",
            "Henri-Georges Clouzot": "亨利-乔治·克鲁佐",
            "Hideki Hamazumm": "浜津守",
            "Hisao Shirai": "白井久男",

            // === I ===
            "Ingmar Bergman": "英格玛·伯格曼",
            "Isao Takahata": "高畑勋",
            "Ivan Dixon": "伊万·迪克森",

            // === J ===
            "James Cameron": "詹姆斯·卡梅隆",
            "James Gunn": "詹姆斯·古恩",
            "James Mangold": "詹姆斯·曼高德",
            "James Marsh": "詹姆斯·马什",
            "James Wan": "温子仁",
            "James Ward Byrkit": "詹姆斯·沃德·布柯特",
            "James Whale": "詹姆斯·惠尔",
            "James Wong": "黄毅瑜",
            "Jan de Bont": "扬·德·邦特",
            "Jared Bush": "杰拉德·布什",
            "Jason Lei Howden": "杰森·李·豪登",
            "Jaume Collet-Serra": "佐米·希尔拉",
            "Jean-Jacques Annaud": "让-雅克·阿诺",
            "Jean-Luc Godard": "让-吕克·戈达尔",
            "Jean-Marc Vallée": "让-马克·瓦雷",
            "Jean-Pierre Jeunet": "让-皮埃尔·热内",
            "Jean-Pierre Melville": "让-皮埃尔·梅尔维尔",
            "Jennifer Lee": "珍妮弗·李",
            "Jeremy Jahns": "杰里米·贾恩斯",
            "Jerry Schatzberg": "杰瑞·沙茨伯格",
            "Jim Jarmusch": "吉姆·贾木许",
            "Jim Sheridan": "吉姆·谢里丹",
            "Joe Russo": "乔·罗素",
            "Joe Wright": "乔·赖特",
            "Joel Coen": "乔尔·科恩",
            "Joel Schumacher": "乔·舒马赫",
            "John Boorman": "约翰·布曼",
            "John Carpenter": "约翰·卡朋特",
            "John Carney": "约翰·卡尼",
            "John Curran": "约翰·克兰",
            "John Ford": "约翰·福特",
            "John G. Avildsen": "约翰·G·艾维尔森",
            "John Hughes": "约翰·休斯",
            "John Huston": "约翰·休斯顿",
            "John Lasseter": "约翰·拉塞特",
            "John McTiernan": "约翰·麦克蒂尔南",
            "John Woo": "吴宇森",
            "Johnnie To": "杜琪峰",
            "Jon Favreau": "乔恩·费儒",
            "Jon Turteltaub": "乔·德特杜巴",
            "Jonathan Demme": "乔纳森·戴米",
            "Jordan Peele": "乔丹·皮尔",
            "Joseph L. Mankiewicz": "约瑟夫·L·曼凯维奇",
            "Joss Whedon": "乔斯·韦登",
            "Juan José Campanella": "胡安·何塞·坎帕内利亚",
            "Julie Taymor": "朱丽·泰莫",
            "Justin Martin": "贾斯汀·马丁",

            // === K ===
            "Katsuhiro Ohtomo": "大友克洋",
            "Katsuhiro Ôtomo": "大友克洋",
            "Keisuke Kinoshita": "木下惠介",
            "Kenneth Lonergan": "肯尼思·洛纳根",
            "Kevin Costner": "凯文·科斯特纳",
            "Kevin Macdonald": "凯文·麦克唐纳",
            "Kirk De Micco": "柯克·德·米科",
            "Krzysztof Kieslowski": "克日什托夫·基耶斯洛夫斯基",

            // === L ===
            "Lana Wachowski": "拉娜·沃卓斯基",
            "Lars von Trier": "拉斯·冯·提尔",
            "Lasse Hallström": "莱塞·霍尔斯道姆",
            "Lee Unkrich": "李·昂克里奇",
            "Lenny Abrahamson": "伦尼·阿伯拉罕森",
            "Leos Carax": "莱奥·卡拉克斯",
            "Lilly Wachowski": "莉莉·沃卓斯基",
            "Louis Leterrier": "路易斯·莱特里尔",
            "Luc Besson": "吕克·贝松",
            "Luis Buñuel": "路易斯·布努埃尔",

            // === M ===
            "M. Night Shyamalan": "M·奈特·沙马兰",
            "Makoto Shinkai": "新海诚",
            "Marc Forster": "马克·福斯特",
            "Marc Webb": "马克·韦布",
            "Martin Brest": "马丁·布莱斯特",
            "Martin McDonagh": "马丁·麦克唐纳",
            "Martin Scorsese": "马丁·斯科塞斯",
            "Mathieu Kassovitz": "马修·卡索维茨",
            "Matt Reeves": "马特·里夫斯",
            "Mel Gibson": "梅尔·吉布森",
            "Michael Bay": "迈克尔·贝",
            "Michael Cimino": "迈克尔·西米诺",
            "Michael Curtiz": "迈克尔·柯蒂斯",
            "Michael Haneke": "迈克尔·哈内克",
            "Michael Mann": "迈克尔·曼",
            "Michel Gondry": "米歇尔·冈瑞",
            "Michelangelo Antonioni": "米开朗基罗·安东尼奥尼",
            "Mike Newell": "迈克·内威尔",
            "Mike Nichols": "迈克·尼科尔斯",
            "Milos Forman": "米洛斯·福尔曼",
            "Morten Tyldum": "莫滕·泰杜姆",

            // === N ===
            "Neil Jordan": "尼尔·乔丹",
            "Neill Blomkamp": "尼尔·布洛姆坎普",
            "Nicholas Ray": "尼古拉斯·雷",
            "Nicolas Winding Refn": "尼古拉斯·温丁·雷弗恩",
            "Nora Twomey": "诺拉·托梅",

            // === O ===
            "Oliver Hirschbiegel": "奥利弗·西斯贝格",
            "Oliver Stone": "奥利弗·斯通",
            "Oriol Paulo": "奥里奥尔·保罗",
            "Orson Welles": "奥逊·威尔斯",

            // === P ===
            "Paolo Sorrentino": "保罗·索伦蒂诺",
            "Paul Greengrass": "保罗·格林格拉斯",
            "Paul Haggis": "保罗·哈吉斯",
            "Paul Thomas Anderson": "保罗·托马斯·安德森",
            "Paul Verhoeven": "保罗·范 霍文",
            "Paul W.S. Anderson": "保罗·W·S·安德森",
            "Pedro Almodóvar": "佩德罗·阿莫多瓦",
            "Penny Marshall": "佩妮·马歇尔",
            "Pete Docter": "彼特·道格特",
            "Peter Bogdanovich": "彼得·博格丹诺维奇",
            "Peter Farrelly": "彼得·法雷里",
            "Peter Jackson": "彼得·杰克逊",
            "Peter Weir": "彼得·威尔",
            "Pierre Coffin": "皮埃尔·科芬",
            "Pierre Morel": "皮埃尔·莫瑞尔",

            // === Q ===
            "Quentin Tarantino": "昆汀·塔伦蒂诺",

            // === R ===
            "Rajkumar Hirani": "拉吉库马尔·希拉尼",
            "Richard Curtis": "理查德·柯蒂斯",
            "Richard Linklater": "理查德·林克莱特",
            "Ridley Scott": "雷德利·斯科特",
            "Rian Johnson": "莱恩·约翰逊",
            "Rob Cohen": "罗伯·科恩",
            "Rob Reiner": "罗伯·莱纳",
            "Robert Altman": "罗伯特·奥特曼",
            "Robert Bresson": "罗伯特·布列松",
            "Robert De Niro": "罗伯特·德尼罗",
            "Robert Rodriguez": "罗伯特·罗德里格兹",
            "Robert Zemeckis": "罗伯特·泽米吉斯",
            "Roberto Benigni": "罗伯托·贝尼尼",
            "Roman Polanski": "罗曼·波兰斯基",
            "Ron Howard": "朗·霍华德",
            "Ruben Fleischer": "鲁本·弗雷斯彻",
            "Rupert Wyatt": "鲁伯特·瓦耶特",
            "Ryan Coogler": "瑞恩·库格勒",

            // === S ===
            "Sam Mendes": "萨姆·门德斯",
            "Sam Peckinpah": "山姆·佩金法",
            "Sam Raimi": "山姆·雷米",
            "Satoshi Kon": "今敏",
            "Sean Penn": "西恩·潘",
            "Sergio Leone": "赛尔乔·莱昂内",
            "Seth MacFarlane": "塞思·麦克法兰",
            "Shawn Levy": "肖恩·利维",
            "Shunji Iwai": "岩井俊二",
            "Sidney Lumet": "西德尼·鲁美特",
            "Simon Wells": "西蒙·威尔斯",
            "Spike Jonze": "斯派克·琼斯",
            "Stanley Kubrick": "斯坦利·库布里克",
            "Stephen Chbosky": "斯蒂芬·切波斯基",
            "Stephen Daldry": "史蒂芬·戴德利",
            "Steven Soderbergh": "史蒂文·索德伯格",
            "Steven Spielberg": "斯蒂芬·斯皮尔伯格",
            "Sydney Pollack": "希德尼·波拉克",

            // === T ===
            "Takeshi Kitano": "北野武",
            "Taylor Hackford": "泰勒·海克福德",
            "Terrence Malick": "泰伦斯·马力克",
            "Terry Gilliam": "特里·吉列姆",
            "Terry Jones": "特里·琼斯",
            "Thomas Vinterberg": "托马斯·温特伯格",
            "Tim Burton": "蒂姆·波顿",
            "Tim Miller": "蒂姆·米勒",
            "Todd Phillips": "托德·菲利普斯",
            "Tom Hooper": "汤姆·霍伯",
            "Tom McCarthy": "托马斯·麦卡锡",
            "Tom Tykwer": "汤姆·提克威",
            "Tony Kaye": "托尼·凯耶",
            "Tony Scott": "托尼·斯科特",

            // === V ===
            "Victor Fleming": "维克多·弗莱明",
            "Vincenzo Natali": "文森佐·纳塔利",
            "Vittorio De Sica": "维托里奥·德·西卡",
            "Volker Schlöndorff": "弗克·施隆多夫",

            // === W ===
            "Werner Herzog": "维尔纳·赫尔佐格",
            "Wes Anderson": "韦斯·安德森",
            "Wes Craven": "韦斯·克雷文",
            "William Friedkin": "威廉·弗莱德金",
            "William Wyler": "威廉·惠勒",
            "Wolfgang Petersen": "沃尔夫冈·彼德森",
            "Wong Kar-Wai": "王家卫",
            "Woody Allen": "伍迪·艾伦",

            // === Y ===
            "Yann Arthus-Bertrand": "扬·阿蒂斯-贝特朗",

            // === Z ===
            "Zack Snyder": "扎克·施奈德",
            "Zhang Yimou": "张艺谋"
            // ... 请确保这里包含原文件中所有的导演映射 ...
        },
        COLORS: ['#00F5FF', '#FF2A6D', '#7B68EE', '#FFD700', '#00FF9F', '#FF6B35']
    };

    // 为了兼容原逻辑中的 DIRECTOR_MAP 查找，这里做一个补丁，
    // 如果你在外部定义了 DIRECTOR_MAP，可以直接引用。
    // 如果原文件里它是硬编码的，请将原文件巨大的 DIRECTOR_MAP 对象完整放入 Constants.DIRECTOR_MAP 中。

    // ================= Part 2: 工具函数 =================
    const Utils = {
        formatNumber: (num) => num.toLocaleString(),
            formatHours: (hours) => hours.toFixed(1),
                getStars: (rating) => '⭐'.repeat(Math.round(rating)),

                   translateCountry(cnName) {
                       return Constants.COUNTRY_MAP[cnName] || cnName;
                   },

                   translateDirector(name) {
                       const map = Constants.DIRECTOR_MAP;
                       // 1. 查表
                       if (map[name]) return map[name];
                       // 2. 处理逗号分隔
                       if (name.includes(',')) {
                           return name.split(',').map(n => map[n.trim()] || n.trim()).join(' / ');
                       }
                       return name;
                   },

                   generateColors(count) {
                       return Constants.COLORS.slice(0, count);
                   },

                   // 核心优化：统一的 CSS 注入器，避免重复 ID 检查
                   injectStyle(id, cssContent) {
                       if (document.getElementById(id)) return;
                       const style = document.createElement('style');
                       style.id = id;
                       style.innerHTML = cssContent;
                       document.head.appendChild(style);
                   },

                   // 核心优化：防抖函数
                   debounce(func, wait) {
                       let timeout;
                       return function() {
                           const context = this, args = arguments;
                           clearTimeout(timeout);
                           timeout = setTimeout(() => func.apply(context, args), wait);
                       };
                   }
    };

    // ================= Part 3: 模板生成 =================
    const Templates = {
        generateAll(data) {
            const sections = [
                this.section1_Summary,
                this.section2_Basic,
                this.section3_DeepDive,
                this.section4_Footprint,
                this.section5_Calendar,
                this.section6_Map,
                this.section7_FiveStar,
                this.section8_Recommend,
                this.section9_Relations
            ];

            // 按顺序执行所有生成函数并拼接
            return sections.map(fn => fn.call(this, data)).join('');
        },

        section1_Summary(data) {
            // 1. 注入悬停样式的 CSS
            Utils.injectStyle('screenshot-hover-style', `
                .screenshot-overlay {
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    width: 100%;
                    padding: 40px 10px 10px 10px; /* 顶部留白给渐变效果 */
                    background: linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.6) 60%, transparent 100%);
                    color: #fff;
                    font-size: 0.9rem;
                    font-weight: bold;
                    text-align: center;
                    opacity: 0; /* 默认隐藏 */
                    transition: opacity 0.3s ease, transform 0.3s ease;
                    transform: translateY(10px); /* 默认下移一点 */
                    pointer-events: none; /* 让鼠标事件穿透，不阻挡图片点击 */
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    z-index: 2;
                    border-radius: 0 0 12px 12px; /* 匹配圆角 */
                }
                .screenshot:hover .screenshot-overlay {
                    opacity: 1;
                    transform: translateY(0);
                }
            `);

            const summary = data['1_Summary'];

            return `
            <div class="merged-section" id="section-gshow_v1">
                <div class="file-separator"><span class="separator-label">个人观影报告</span></div>
                <div class="container">
                    <main class="glass-container">
                        <header class="header-title fade-in">
                            <h1>个人观影报告</h1>
                            <p>一场光影的巡礼</p>
                        </header>
                        
                        <section class="stat-cards-container scroll-animate">
                            <article class="stat-card wide">
                                <p class="stat-card__value">${summary.total_movies}</p>
                                <p class="stat-card__label">总观影量（部）</p>
                            </article>
                            <article class="stat-card wide">
                                <p class="stat-card__value">${Utils.formatHours(summary.total_hours)}</p>
                                <p class="stat-card__label">总观影时长（小时）</p>
                            </article>
                            <article class="stat-card">
                                <p class="stat-card__value">${(summary.total_hours / (summary.total_movies || 1)).toFixed(1)}</p>
                                <p class="stat-card__label">平均时长（小时）</p>
                            </article>
                            <article class="stat-card">
                                <p class="stat-card__value">${summary.avg_rating.toFixed(1)}</p>
                                <p class="stat-card__label">平均评分</p>
                            </article>
                            <article class="stat-card special">
                                <p class="stat-card__value">${Utils.formatNumber(summary.total_comment_chars)}</p>
                                <p class="stat-card__label">短评字数</p>
                            </article>
                        </section>

                        <section class="scroll-animate">
                            <h2 class="section-title">精彩瞬间 · 截图墙</h2>
                            <div class="screenshot-wall">
                                ${summary.screenshot_wall_sample.map((item, i) => `
                                    <div class="screenshot fade-in" style="animation-delay: ${i * 0.05}s" title="${item.title}">
                                        <img alt="${item.title}" src="${item.path}" onerror="this.src='https://via.placeholder.com/400x225?text=No+Img'"/>
                                        <div class="screenshot-overlay">${item.title}</div>
                                    </div>
                                `).join('')}
                            </div>
                        </section>
                    </main>
                </div>
            </div>`;
        },

        section2_Basic(data) {
            return `
            <div class="merged-section" id="section-gshow_v2">
            <div class="file-separator"><span class="separator-label">观影分析</span></div>
            <div class="container">
            <main class="glass-container">
            <header class="header-title fade-in">
            <h1>我的观影数据分析</h1>
            <p>数据视角下的光影世界</p>
            </header>
            <section class="charts-grid">
            <div class="chart-container scroll-animate">
            <h3 class="chart-title">评分分布</h3>
            <div class="chart" id="rating-pie_v2"></div>
            </div>
            <div class="chart-container scroll-animate">
            <h3 class="chart-title">类型占比</h3>
            <div class="chart" id="genre-proportion-pie"></div>
            </div>
            <div class="chart-container full-width scroll-animate">
            <h3 class="chart-title">每季度电影平均分分布</h3>
            <div class="chart" id="quarter-scatter"></div>
            </div>
            <div class="chart-container full-width scroll-animate">
            <h3 class="chart-title">每月观影数量统计</h3>
            <div class="chart" id="monthly-count-bar"></div>
            </div>
            <div class="chart-container full-width scroll-animate">
            <h3 class="chart-title">最爱的类型 TopN</h3>
            <div class="chart" id="genre-logbar"></div>
            </div>
            </section>
            </main>
            </div>
            </div>`;
        },

        section3_DeepDive(data) {
            return `
            <div class="merged-section" id="section-gshow_v3">
            <div class="file-separator"><span class="separator-label">深度观影分析</span></div>
            <div class="container">
            <main class="glass-container">
            <header class="header-title fade-in">
            <h1>深度观影数据分析</h1>
            <p>探索你的电影世界</p>
            </header>
            <section class="charts-grid">
            <div class="chart-container full-width scroll-animate">
            <h3 class="chart-title">年代统计直方图（每十年）</h3>
            <div class="chart" id="decade-histogram"></div>
            </div>
            <div class="chart-container full-width scroll-animate">
            <h3 class="chart-title">每年新认识的导演(看过两部才纳入统计)</h3>
            <div id="new-directors-list" class="new-directors-container"></div>
            </div>
            <div class="chart-container full-width scroll-animate">
            <h3 class="chart-title">影人偏好</h3>
            <div class="person-lists-container">
            <div class="person-list-card" id="top-actors-list"><h4>最常看的影人 (Top 20)</h4></div>
            <div class="person-list-card" id="top-writers-list"><h4>最常看的编剧 (Top 10)</h4></div>
            </div>
            </div>
            <div class="chart-container full-width scroll-animate">
            <h3 class="chart-title">关键词云 (100个)</h3>
            <div class="keyword-tags" id="keyword-cloud"></div>
            </div>
            <div class="chart-container full-width scroll-animate">
            <h3 class="chart-title">全库冷门探索 (Top 10)</h3>
            <div class="rare-genres" id="rare-genres-list"></div>
            </div>
            </section>
            </main>
            </div>
            </div>`;
        },

        section4_Footprint(data) {
            return `
            <div class="merged-section" id="section-gshow_v4">
            <div class="file-separator"><span class="separator-label">全球光影足迹</span></div>
            <div class="container">
            <main class="glass-container">
            <header class="header-title fade-in">
            <h1>全球光影足迹</h1>
            <p>GEOGRAPHY & LINGUISTICS ANALYSIS</p>
            </header>
            <section class="charts-grid">
            <div class="chart-container full-width scroll-animate">
            <h3 class="chart-title">制作地区分布 (对数尺度)</h3>
            <div class="chart" id="region-log-chart"></div>
            </div>
            <div class="chart-container full-width scroll-animate">
            <h3 class="chart-title">原声语言偏好</h3>
            <div class="chart" id="language-rose-chart" style="height: 500px;"></div>
            </div>
            </section>
            </main>
            </div>
            </div>`;
        },

        section5_Calendar(data) {
            return `
            <div class="merged-section" id="section-gshow_v5">
            <div class="file-separator"><span class="separator-label">观影日历热力图</span></div>
            <div class="v5-wrap">
            <div class="v5-panel">
            <div class="v5-header">
            <div class="v5-title">
            <h1>观影日历 · 半年视图</h1>
            <p>精确到每天的观影数量，优雅高阶风格。</p>
            </div>
            <div class="v5-stats">
            <div class="v5-stat"><div class="num" id="stat-total">0</div><div>总观影数</div></div>
            <div class="v5-stat"><div class="num" id="stat-days">0</div><div>观影天数</div></div>
            <div class="v5-stat"><div class="num" id="stat-avg">0</div><div>日均观影</div></div>
            <div class="v5-stat"><div class="num" id="stat-max">0</div><div>单日最高</div></div>
            </div>
            </div>
            <div class="v5-legend">
            <div class="v5-legend-swatch" style="background: rgba(255,255,255,0.1)"></div>0 部
            <div style="width:10px"></div>
            <div class="v5-legend-swatch" style="background: #8A6CFF"></div>1-2 部
            <div style="width:10px"></div>
            <div class="v5-legend-swatch" style="background: #FF5C9D"></div>3+ 部
            </div>
            <div id="years-root"></div>
            </div>
            </div>
            </div>`;
        },

        section6_Map(data) {
            return `
            <div class="merged-section" id="section-gshow_v6">
            <div class="file-separator"><span class="separator-label">全球观影热力对数地图</span></div>
            <div class="container">
            <div class="glass-container fade-in">
            <div class="header-title">
            <h1>全球观影热力对数地图（10^(n)）</h1>
            <p>数据驱动的光影世界之旅</p>
            </div>
            <div id="map-section">
            <div class="map-container">
            <div id="world-map_v6"></div>
            </div>
            <div class="stats-grid">
            <div class="v6-stat-card"><span class="v6-stat-number" id="total-countries">0</span><div>观影国家/地区</div></div>
            <div class="v6-stat-card"><span class="v6-stat-number" id="total-movies">0</span><div>总观影量</div></div>
            <div class="v6-stat-card"><span class="v6-stat-number" id="top-country">-</span><div>观影最多地区</div></div>
            </div>
            </div>
            </div>
            </div>
            </div>`;
        },

        section7_FiveStar(data) {
            return `
            <div class="merged-section" id="section-gshow_v7">
            <div class="file-separator"><span class="separator-label">五星金榜与评论统计</span></div>
            <div class="container">
            <main class="glass-container">
            <header class="header-title fade-in">
            <h1>我的观影数据分析</h1>
            <p>五星佳片与影评时光</p>
            </header>
            <section class="five-star-section scroll-animate">
            <h2 class="section-title">五星金榜</h2>
            <div id="five-star-content"></div>
            </section>
            <section class="five-star-posters scroll-animate">
            <h2 class="section-title">五星海报墙</h2>
            <div id="five-star-poster-grid" class="poster-grid"></div>
            </section>
            <section class="charts-grid">
            <div class="chart-container full-width scroll-animate">
            <h3 class="chart-title">每月电影评论字数统计</h3>
            <div class="chart" id="monthly-words-chart"></div>
            </div>
            <div class="chart-container full-width scroll-animate">
            <h3 class="chart-title">我的短评高频词</h3>
            <div class="keyword-tags" id="comment-cloud" style="height: 400px; overflow-y: auto;"></div>
            </div>
            </section>
            </main>
            </div>
            </div>`;
        },

        section8_Recommend(data) {
            return `
            <div class="merged-section" id="section-gshow_v8">
            <div class="file-separator"><span class="separator-label">电影推荐分析</span></div>
            <div class="container">
            <header class="header-title">
            <h1>电影推荐分析</h1>
            <p>发现你的独特观影品味</p>
            </header>
            <main class="movies-section">
            <section class="section-container">
            <h2 style="color: #FF2A6D; margin-bottom: 1rem;">👎 不合口味</h2>
            <p style="color: #BDC3C7; margin-bottom: 1rem;">个人评分远低于大众评分</p>
            <div id="not-my-cup-content"></div>
            </section>
            <section class="section-container">
            <h2 style="color: #00F5FF; margin-bottom: 1rem;">💎 意外发现</h2>
            <p style="color: #BDC3C7; margin-bottom: 1rem;">大众低分但你觉得很赞</p>
            <div id="unexpected-content"></div>
            </section>
            </main>
            </div>
            </div>`;
        },

        section9_Relations(data) {
            return `
            <div class="merged-section" id="section-gshow_v9">
            <div class="file-separator"><span class="separator-label">多维度关系洞察</span></div>
            <div class="container">
            <main class="glass-container">
            <header class="header-title fade-in">
            <h1>电影数据分析中心</h1>
            <p>多维度关系洞察</p>
            </header>
            <section class="charts-grid">
            <div class="chart-container scroll-animate">
            <h3 class="chart-title">评分与电影出品年代</h3>
            <div class="chart" id="rating-decade"></div>
            </div>
            <div class="chart-container scroll-animate">
            <h3 class="chart-title">评分与观看年份</h3>
            <div class="chart" id="rating-watch-year"></div>
            </div>
            <div class="chart-container scroll-animate">
            <h3 class="chart-title">评分与时长分布</h3>
            <div class="chart" id="rating-duration"></div>
            </div>
            <div class="chart-container scroll-animate">
            <h3 class="chart-title">评分与类型关系</h3>
            <div class="chart" id="rating-genre-chart"></div>
            </div>
            </section>
            </main>
            </div>
            </div>`;
        }
    };

    // ================= Part 4: 图表与内容渲染逻辑 =================
    const Charts = {
        // 注册表：用于 resize
        instances: [],

        // 通用图表初始化方法 (核心优化)
        initChart(domId, option) {
            const dom = document.getElementById(domId);
            if (!dom) return null;
            const chart = echarts.init(dom);
            // 合并默认配置与特定配置
            const baseOption = {
                backgroundColor: 'transparent',
                textStyle: { fontFamily: 'sans-serif' },
                ...option
            };
            chart.setOption(baseOption);
            this.instances.push(chart);
            return chart;
        },

        // --- V2 ---
        initV2RatingPie(data) {
            const ratingDist = data['5_Preferences_Cross_Analysis'].rating_distribution;
            const pieData = Object.entries(ratingDist).map(([rating, count]) => ({ value: count, name: `${rating}星` }));

            this.initChart('rating-pie_v2', {
                tooltip: { trigger: 'item' },
                series: [{
                    type: 'pie', radius: ['40%', '70%'], center: ['50%', '50%'],
                    itemStyle: { borderRadius: 10, borderColor: '#0f0c29', borderWidth: 2 },
                    label: { color: '#fff' },
                    data: pieData, color: Utils.generateColors(pieData.length)
                }]
            });
        },

        initV2GenrePie(data) {
            const genres = data['3_Content_Analysis'].genres.chinese.slice(0, 10);
            const pieData = genres.map(g => ({ value: g.count, name: g.name }));

            this.initChart('genre-proportion-pie', {
                tooltip: { trigger: 'item' },
                series: [{
                    type: 'pie', radius: ['40%', '70%'],
                    itemStyle: { borderRadius: 10, borderColor: '#0f0c29', borderWidth: 2 },
                    label: { color: '#fff' },
                    data: pieData, color: Utils.generateColors(pieData.length)
                }]
            });
        },

        initV2QuarterScatter(data) {
            const quarterStats = data['2_Timeline'].quarterly_stats;
            const scatterData = quarterStats.flatMap((q, qIndex) =>
            (q.ratings || []).map(r => [qIndex + (Math.random() - 0.5) * 0.6, r])
            );

            this.initChart('quarter-scatter', {
                tooltip: { trigger: 'item' },
                xAxis: { type: 'category', data: quarterStats.map(q => q.quarter), axisLabel: { color: '#fff' }, splitLine: { show: false } },
                           yAxis: { type: 'value', min: 0, max: 5, axisLabel: { color: '#fff' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } } },
                           series: [{
                               type: 'scatter', symbolSize: 20, data: scatterData,
                               itemStyle: { color: '#00F5FF', shadowBlur: 10, shadowColor: '#00F5FF' }
                           }]
            });
        },

        initV2MonthlyCount(data) {
            const stats = data['2_Timeline'].monthly_stats;
            this.initChart('monthly-count-bar', {
                tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                grid: { containLabel: true, left: '5%', right: '5%', top: '15%', bottom: '5%' },
                xAxis: { type: 'category', data: stats.map(i => i.month), axisLabel: { color: '#fff', fontSize: 12 }, axisLine: { lineStyle: { color: 'rgba(255,255,255,0.3)' } } },
                           yAxis: { type: 'value', minInterval: 1, axisLabel: { color: '#fff' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } } },
                           series: [{
                               name: '观影数', type: 'bar', barWidth: '40%', data: stats.map(i => i.count),
                           itemStyle: { borderRadius: [5, 5, 0, 0], color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#00F5FF' }, { offset: 1, color: '#0072ff' }]) },
                           label: { show: true, position: 'top', color: '#fff', fontSize: 14, fontWeight: 'bold' },
                           animationDelay: (idx) => idx * 100
                           }]
            });
        },

        initV2GenreBar(data) {
            const dom = document.getElementById('genre-logbar');
            const genres = data['3_Content_Analysis'].genres.chinese.slice(0, 50).reverse();
            // 动态设置高度
            dom.style.height = `${genres.length * 36 + 80}px`;
            dom.style.maxHeight = 'none';

            this.initChart('genre-logbar', {
                tooltip: { trigger: 'axis', formatter: '{b}: {c} 部' },
                grid: { containLabel: true, left: '2%', right: '6%', top: '30', bottom: '20' },
                xAxis: { type: 'log', min: 1, logBase: 10, position: 'top', axisLabel: { color: '#aaa' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                           yAxis: {
                               type: 'category', data: genres.map(g => g.name),
                           axisLabel: { color: '#fff', interval: 0, fontSize: 15, fontWeight: 'bold', margin: 16 },
                           axisTick: { show: false }, axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
                           },
                           series: [{
                               type: 'bar', data: genres.map(g => g.count), barWidth: 14,
                           itemStyle: { borderRadius: [0, 7, 7, 0], color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: '#7B68EE' }, { offset: 1, color: '#00F5FF' }]) },
                           label: { show: true, position: 'right', color: '#00F5FF', fontSize: 14, fontWeight: 'bold', formatter: '{c}' }
                           }]
            });
        },

        // --- V3 ---
        initV3DecadeChart(data) {
            const decadeData = data['3_Content_Analysis'].decadal_premieres;
            const decades = Object.keys(decadeData).sort();

            this.initChart('decade-histogram', {
                tooltip: { trigger: 'axis' },
                xAxis: { type: 'category', data: decades, axisLabel: { color: '#fff' } },
                yAxis: { type: 'value', axisLabel: { color: '#fff' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } } },
                           series: [{
                               type: 'bar', data: decades.map(d => decadeData[d]),
                           itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#FF2A6D' }, { offset: 1, color: '#7B68EE' }]) }
                           }]
            });
        },

        renderDirectorList(data) {
            const container = document.getElementById('new-directors-list');
            const directorsData = data['4_People_Analysis'].new_director_discovery;

            Utils.injectStyle('director-style-injected', `
            .director-names-wrapper { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; margin-bottom: 24px; padding-left: 4px; }
            .director-name-tag { background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 5px 12px; font-size: 0.9rem; font-weight: 700; color: #e0e0e0; transition: all 0.3s ease; cursor: default; letter-spacing: 0.5px; }
            .director-name-tag:hover { background: rgba(123, 104, 238, 0.4); border-color: #7B68EE; color: #fff; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(123, 104, 238, 0.3); }
            .director-year-header { display: flex; align-items: baseline; gap: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px; }
            .dy-year { font-size: 1.8rem; font-weight: 800; background: linear-gradient(to right, #fff, #ccc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-family: 'Arial Black', sans-serif; letter-spacing: -1px; }
            .dy-count-pill { background: rgba(0, 245, 255, 0.15); border: 1px solid rgba(0, 245, 255, 0.4); color: #00F5FF; padding: 2px 10px; border-radius: 20px; font-size: 0.85rem; font-weight: bold; display: flex; align-items: center; gap: 4px; box-shadow: 0 0 10px rgba(0, 245, 255, 0.1); }
            `);

            container.innerHTML = directorsData.map(d => `
            <div style="margin-bottom: 1.5rem;">
            <div class="director-year-header">
            <div class="dy-year">${d.year}</div>
            <div class="dy-count-pill"><span>✦</span> <span>新遇 ${d.count} 位</span></div>
            </div>
            <div class="director-names-wrapper">
            ${d.list.map(name => `<span class="director-name-tag">${Utils.translateDirector(name)}</span>`).join('')}
            </div>
            </div>
            `).join('');
        },

        renderPersonList(containerId, list) {
            const container = document.getElementById(containerId);
            container.innerHTML = `<h4>${container.querySelector('h4')?.innerText || 'List'}</h4>` +
            list.map((item, i) => `
            <div class="person-item"><span>${i + 1}. ${item.name}</span><span class="count">${item.count}部</span></div>
            `).join('');
        },

        renderCloud(containerId, words) {
            const container = document.getElementById(containerId);
            if (!words || words.length === 0) {
                container.innerHTML = '<div style="color:#666; text-align:center; margin-top:50px;">暂无数据</div>';
                return;
            }

            Utils.injectStyle('keyword-style-compact', `
            #keyword-cloud, #comment-cloud { max-height: 50vh; overflow-y: auto; justify-content: center; align-content: center; padding: 10px 20px; gap: 10px 12px; display: flex; flex-wrap: wrap; }
            #keyword-cloud::-webkit-scrollbar, #comment-cloud::-webkit-scrollbar { width: 6px; }
            #keyword-cloud::-webkit-scrollbar-thumb, #comment-cloud::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 3px; }
            .keyword-tag { padding: 3px 10px; border-radius: 12px; line-height: 1.2; border: 1px solid rgba(123, 104, 238, 0.2); background: rgba(123, 104, 238, 0.1); color: #e0e0e0; cursor: default; white-space: nowrap; transition: all 0.3s ease; }
            .keyword-tag.highlight { background: linear-gradient(135deg, #00F5FF, #7B68EE); border: none; color: #000; font-weight: 800; box-shadow: 0 4px 10px rgba(0, 245, 255, 0.3); }
            .keyword-tag:hover { transform: scale(1.1); z-index: 10; background: rgba(0, 245, 255, 0.8); color: #000; border-color: transparent; }
            `);

            container.innerHTML = '';
            const maxCount = words[0].count;
            const minCount = words[words.length - 1].count;
            const [minSize, maxSize] = [0.8, 2.5];

            words.forEach((k, i) => {
                const span = document.createElement('span');
                span.className = 'keyword-tag' + (i < 5 ? ' highlight' : '');
                span.innerText = k.name;
                span.title = `出现次数: ${k.count}`;
                const weight = maxCount === minCount ? 0 : (Math.log(k.count) - Math.log(minCount)) / (Math.log(maxCount) - Math.log(minCount));
                span.style.fontSize = `${(minSize + weight * (maxSize - minSize)).toFixed(2)}rem`;
                if (i >= 5) span.style.opacity = 0.6 + (weight * 0.4);
                container.appendChild(span);
            });
        },

        renderRareGenres(data) {
            const container = document.getElementById('rare-genres-list');
            const list = data['3_Content_Analysis'].rare_genres_global;
            if (!list || list.length === 0) {
                container.innerHTML = '<div style="width:100%; text-align:center; color:#666;">暂无数据</div>';
                return;
            }

            container.innerHTML = list.map(g => {
                const firstMovie = g.movies && g.movies.length > 0 ? g.movies[0].split('/')[0].trim() : '';
                return `
                <div class="rare-genre-item" title="包含电影：${g.movies ? g.movies.join('、') : ''}">
                <div class="rare-genre-name">${g.genre}</div>
                <div style="font-size: 0.85rem; color: #888; margin: 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;">${firstMovie}</div>
                <div class="rare-genre-count" style="font-size: 1.2rem;">${g.count} <span style="font-size:0.8rem; font-weight:normal; color:#666;">部</span></div>
                </div>`;
            }).join('');
        },

        // --- V4 ---
        initV4RegionChart(data) {
            const dom = document.getElementById('region-log-chart');
            const regions = data['3_Content_Analysis'].regions_languages.regions_zh;
            const regionArray = Object.entries(regions).map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count).reverse();

            dom.style.height = `${regionArray.length * 36 + 80}px`;
            dom.style.maxHeight = 'none';

            this.initChart('region-log-chart', {
                tooltip: { trigger: 'axis', formatter: '{b}: {c} 部' },
                grid: { containLabel: true, left: '2%', right: '8%', top: '30', bottom: '20' },
                xAxis: { type: 'log', min: 1, logBase: 10, position: 'top', axisLabel: { color: '#aaa' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                           yAxis: {
                               type: 'category', data: regionArray.map(r => r.name),
                           axisLabel: { color: '#fff', interval: 0, fontSize: 15, fontWeight: 'bold', margin: 12 },
                           axisTick: { show: false }, axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
                           },
                           series: [{
                               type: 'bar', data: regionArray.map(r => r.count), barWidth: 14,
                           itemStyle: { borderRadius: [0, 7, 7, 0], color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: '#00F5FF' }, { offset: 1, color: '#7B68EE' }]) },
                           label: { show: true, position: 'right', color: '#fff', fontSize: 14, fontWeight: 'bold', formatter: '{c}' }
                           }]
            });
        },

        initV4LanguageChart(data) {
            const languages = data['3_Content_Analysis'].regions_languages.langs_zh;
            const langData = Object.entries(languages)
            .map(([name, count]) => ({ name, value: Math.log10(count) + 1, rawValue: count }))
            .sort((a, b) => b.value - a.value);

            this.initChart('language-rose-chart', {
                tooltip: {
                    trigger: 'item',
                    formatter: p => `${p.marker} ${p.name}<br/><span style="color:#aaa;">观影:</span> <b>${p.data.rawValue}</b> 部<br/><span style="color:#aaa;">占比:</span> ${p.percent}%`
                },
                legend: {
                    type: 'scroll', orient: 'vertical', right: 10, top: 20, bottom: 20, textStyle: { color: '#ccc', fontSize: 12 },
                    formatter: name => { const item = langData.find(d => d.name === name); return item ? `${name} (${item.rawValue})` : name; },
                        data: langData.map(d => d.name)
                },
                series: [{
                    name: '原声语言', type: 'pie', radius: [30, '75%'], center: ['40%', '50%'], roseType: 'area',
                    itemStyle: { borderRadius: 5, borderColor: '#0f0c29', borderWidth: 2 },
                    label: { show: true, color: '#fff', fontSize: 13, formatter: p => `${p.name} ${p.data.rawValue}` },
                    labelLine: { length: 10, length2: 10, smooth: true, lineStyle: { color: 'rgba(255, 255, 255, 0.3)' } },
                           data: langData, color: Utils.generateColors(10).concat(['#F0F', '#1E90FF', '#ADFF2F', '#FF4500'])
                }]
            });
        },

        // --- V5 日历 ---
        initV5Calendar(data) {
            const dailyCounts = data['2_Timeline'].daily_counts;

            // 更新统计板
            const totalMovies = dailyCounts.reduce((sum, d) => sum + d.count, 0);
            const totalDays = dailyCounts.length;
            document.getElementById('stat-total').innerText = totalMovies;
            document.getElementById('stat-days').innerText = totalDays;
            document.getElementById('stat-avg').innerText = totalDays ? (totalMovies / totalDays).toFixed(1) : 0;
            document.getElementById('stat-max').innerText = dailyCounts.length ? Math.max(...dailyCounts.map(d => d.count)) : 0;

            if (!dailyCounts.length) return;

            const countMap = new Map(dailyCounts.map(d => [d.date, d.count]));
            const startYear = parseInt(dailyCounts[0].date.split('-')[0]);
            const endYear = parseInt(dailyCounts[dailyCounts.length - 1].date.split('-')[0]);
            const root = document.getElementById('years-root');
            root.innerHTML = '';

            for (let year = startYear; year <= endYear; year++) {
                const halves = { H1: [], H2: [] };
                let curr = new Date(year, 0, 1);
                const end = new Date(year, 11, 31);

                while (curr <= end) {
                    const y = curr.getFullYear(), m = curr.getMonth() + 1, d = curr.getDate();
                    const dateStr = `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
                    const half = m <= 6 ? 'H1' : 'H2';
                    halves[half].push([dateStr, countMap.get(dateStr) || 0]);
                    curr.setDate(curr.getDate() + 1);
                }

                // DOM 构建
                const block = document.createElement('div');
                block.className = 'v5-year-block';
                block.innerHTML = `<div style="color:#7B68EE; font-weight:bold; margin-bottom:10px; font-size:1.2rem">${year} 年</div><div class="v5-half-grid"></div>`;
                const grid = block.querySelector('.v5-half-grid');

                ['H1', 'H2'].forEach(half => {
                    const id = `cal-${year}-${half}`;
                    const card = document.createElement('div');
                    card.className = 'v5-half-card';
                    card.innerHTML = `<div style="color:#aaa; font-size:12px; margin-bottom:5px">${half === 'H1' ? '上半年' : '下半年'}</div><div id="${id}" class="v5-chart-slot"></div>`;
                    grid.appendChild(card);

                    setTimeout(() => {
                        this.initChart(id, {
                            tooltip: { position: 'top', formatter: p => `${p.value[0]}<br/>观影: ${p.value[1]} 部` },
                            visualMap: { min: 0, max: 4, show: false, inRange: { color: ['#5f5891ff', '#6D4C85', '#F58A65', '#FAD961'] } },
                            calendar: {
                                top: 30, left: 30, right: 30, cellSize: ['auto', 20],
                                range: half === 'H1' ? [`${year}-01-01`, `${year}-06-30`] : [`${year}-07-01`, `${year}-12-31`],
                                itemStyle: { borderColor: '#36405F', borderWidth: 1 },
                                yearLabel: { show: false }, dayLabel: { color: '#666' }, monthLabel: { color: '#999' }, splitLine: { show: false }
                            },
                            series: [{ type: 'heatmap', coordinateSystem: 'calendar', data: halves[half] }]
                        });
                    }, 100);
                });
                root.appendChild(block);
            }
        },

        // --- V6 地图 ---
        initV6Map(data) {
            const regions = data['3_Content_Analysis'].regions_languages.regions_zh;
            const chartDom = document.getElementById("world-map_v6");
            if(!chartDom) return;

            const chart = echarts.init(chartDom);
            this.instances.push(chart);

            const mapData = Object.entries(regions).map(([cn, count]) => ({
                name: Utils.translateCountry(cn),
                                                                          value: Math.log10(count),
                                                                          rawValue: count
            }));

            // 更新统计字
            document.getElementById('total-countries').innerText = Object.keys(regions).length;
            document.getElementById('total-movies').innerText = data['1_Summary'].total_movies;
            document.getElementById('top-country').innerText = Object.entries(regions).sort((a,b) => b[1]-a[1])[0]?.[0] || '-';

            fetch('https://cdn.jsdelivr.net/npm/echarts/map/json/world.json')
            .then(r => r.json())
            .then(worldJson => {
                echarts.registerMap('world', worldJson);
                chart.setOption({
                    backgroundColor: 'transparent',
                    tooltip: { trigger: 'item', formatter: p => p.data ? `${p.name}<br/>观影: ${p.data.rawValue} 部` : p.name },
                    visualMap: {
                        min: 0, max: Math.log10(Math.max(...Object.values(regions)) || 1),
                                calculable: true, text: ['High', 'Low'], left: 'left', top: 'bottom', textStyle: { color: '#fff' },
                                inRange: { color: ['#5f5891ff', '#6D4C85', '#F58A65', '#FAD961'] }
                    },
                    series: [{
                        type: 'map', map: 'world', roam: true,
                        itemStyle: { areaColor: '#1a1a2e', borderColor: '#444' },
                        emphasis: { itemStyle: { areaColor: '#00F5FF' }, label: { color: '#000' } },
                        data: mapData
                    }]
                });
            })
            .catch(() => chartDom.innerHTML = "<div style='text-align:center; padding-top:200px; color:#999;'>地图数据加载需联网...</div>");
        },

        // --- V7 五星 ---
        initV7FiveStar(data) {
            const movies = data['5_Preferences_Cross_Analysis']?.five_star_movies || [];
            const contentContainer = document.getElementById('five-star-content');
            const posterContainer = document.getElementById('five-star-poster-grid');

            if (movies.length === 0) {
                contentContainer.innerHTML = '<p style="text-align:center; color:#666;">暂无五星电影数据。</p>';
                return;
            }

            Utils.injectStyle('fivestar-style-injected', `
            .five-star-cloud { display: flex; flex-wrap: wrap; gap: 10px 12px; justify-content: center; padding: 10px 0 30px 0; }
            .fs-chip { display: inline-flex; align-items: center; background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(0, 245, 255, 0.2); border-radius: 20px; padding: 6px 16px; text-decoration: none; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); position: relative; overflow: hidden; }
            .fs-chip:hover { background: rgba(0, 245, 255, 0.1); border-color: #00F5FF; transform: translateY(-3px); box-shadow: 0 4px 12px rgba(0, 245, 255, 0.2); }
            .fs-title { color: #fff; font-weight: 600; font-size: 0.95rem; margin-right: 10px; letter-spacing: 0.5px; }
            .fs-date { color: rgba(255, 255, 255, 0.5); font-size: 0.8rem; font-family: monospace; padding-left: 10px; border-left: 1px solid rgba(255, 255, 255, 0.15); }
            .fs-chip:hover .fs-date { color: rgba(255, 255, 255, 0.9); border-left-color: rgba(0, 245, 255, 0.5); }
            .poster-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 6px; padding: 15px; background: rgba(0,0,0,0.1); border-radius: 12px; margin-top: 10px; box-shadow: inset 0 0 20px rgba(0,0,0,0.3); }
            .poster-grid-item { position: relative; width: 100%; padding-bottom: 140%; overflow: hidden; border-radius: 4px; filter: grayscale(30%); transition: all 0.4s ease; }
            .poster-grid-item:hover { transform: scale(1.15); z-index: 10; filter: grayscale(0%); box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            .poster-grid-item img { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; }
            .poster-grid-item .overlay { position: absolute; bottom: 0; left: 0; width: 100%; padding: 20px 5px 5px 5px; background: linear-gradient(to top, rgba(0,0,0,0.9), transparent); color: #fff; font-size: 0.7rem; text-align: center; opacity: 0; transition: opacity 0.3s; pointer-events: none;}
            .poster-grid-item:hover .overlay { opacity: 1; }
            `);

            // 生成 Chip 列表
            contentContainer.innerHTML = `<div class="five-star-cloud">
            ${movies.map(m => `
                <a href="${m.douban_url || '#'}" target="_blank" class="fs-chip" title="${m.title}">
                <span class="fs-title">${m.title || '未知电影'}</span>
                <span class="fs-date">${m.watch_date || '-'}</span>
                </a>
                `).join('')}
                </div>`;

                // 生成海报墙
                posterContainer.innerHTML = movies.filter(m => m.poster).map(m => {
                    const posterPath = (m.poster.startsWith('http') || m.poster.startsWith('../')) ? m.poster : `../../resources/${m.poster}`;
                    return `
                    <a href="${m.douban_url || '#'}" target="_blank" class="poster-grid-item" title="${m.title}">
                    <img src="${posterPath}" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 100 140\' fill=\'%23333\'%3E%3Ctext x=\'50%\' y=\'50%\' font-family=\'Arial\' font-size=\'12\' text-anchor=\'middle\' dominant-baseline=\'middle\' fill=\'%23666\'%3ENo Img%3C/text%3E%3C/svg%3E';"/>
                    <div class="overlay">${m.title}</div>
                    </a>`;
                }).join('');
        },

        initV7MonthlyWords(data) {
            const stats = data['2_Timeline'].monthly_stats;
            this.initChart('monthly-words-chart', {
                tooltip: { trigger: 'axis', formatter: '{b}<br/>✍️ 评论: {c} 字' },
                grid: { containLabel: true, left: '5%', right: '5%', top: '15%', bottom: '10%' },
                xAxis: { type: 'category', data: stats.map(i => i.month), axisLabel: { color: '#aaa', fontSize: 11 }, axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } } },
                           yAxis: { type: 'value', name: '字数', nameTextStyle: { color: '#aaa', padding: [0, 0, 0, 20] }, axisLabel: { color: '#aaa' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                           series: [{
                               name: '短评字数', type: 'line', smooth: true, symbol: 'none', data: stats.map(i => i.comment_chars),
                           lineStyle: { width: 3, color: '#FFD700' },
                           areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(255, 215, 0, 0.3)' }, { offset: 1, color: 'rgba(255, 215, 0, 0.01)' }]) }
                           }]
            });
        },

        // --- V8 推荐 ---
        renderRecommendations(data) {
            const dev = data['5_Preferences_Cross_Analysis'].taste_deviation;
            const renderCards = (containerId, list, isGood) => {
                const container = document.getElementById(containerId);
                container.innerHTML = list.map(m => `
                <div class="v8-movie-card">
                <h3 style="color: #fff;">${m.title}</h3>
                <div style="color: ${isGood ? '#00F5FF' : '#FF2A6D'}; font-weight: bold; margin-top: 0.5rem;">
                我的评分: ${m.my} | 大众: ${isGood ? m.pub_min : m.pub_max} | ${isGood ? '超大众' : '差值'}: ${m.diff > 0 ? '+' : ''}${m.diff.toFixed(2)}
                </div>
                </div>
                `).join('');
            };
            renderCards('not-my-cup-content', dev.not_my_cup_of_tea_top20.slice(0, 15), false);
            renderCards('unexpected-content', dev.unexpected_discoveries_top20.slice(0, 15), true);
        },

        // --- V9 多维 ---
        initV9Charts(data) {
            const cm = data['5_Preferences_Cross_Analysis'].cross_metrics;

            // 通用配置工厂
            const makeOption = (xData, yData, type, color1, color2) => ({
                tooltip: { trigger: 'axis' },
                xAxis: { type: 'category', data: xData, axisLabel: { color: '#fff', rotate: type === 'bar' && xData.length > 8 ? 30 : 0 } },
                yAxis: { type: 'value', min: 2, max: 5, axisLabel: { color: '#fff' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } } },
                                                                        series: [{
                                                                            type: type, data: yData, smooth: true,
                                                                            itemStyle: { borderRadius: type === 'bar' ? [5, 5, 0, 0] : 0, color: color2 ? new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: color1 }, { offset: 1, color: color2 }]) : color1 },
                                                                        lineStyle: { width: 3 },
                                                                        areaStyle: type === 'line' ? { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: color1 + '4D' }, { offset: 1, color: color1 + '0D' }]) } : undefined
                                                                        }]
            });

            // 1. 年代
            const decades = Object.keys(cm.rating_vs_decade).sort();
            this.initChart('rating-decade', makeOption(decades, decades.map(k => cm.rating_vs_decade[k]), 'line', '#00F5FF'));

            // 2. 观看年份
            const years = Object.keys(cm.rating_vs_watch_year).sort();
            this.initChart('rating-watch-year', makeOption(years, years.map(k => cm.rating_vs_watch_year[k]), 'bar', '#FFD700', '#FF6B35'));

            // 3. 时长
            const durs = Object.keys(cm.rating_vs_duration_bin).sort();
            this.initChart('rating-duration', makeOption(durs, durs.map(k => cm.rating_vs_duration_bin[k]), 'bar', '#FF6B35', '#FF2A6D'));

            // 4. 类型 (横向条形图特殊处理)
            const genres = Object.entries(cm.rating_vs_genre_zh).sort((a, b) => b[1] - a[1]).slice(0, 10);
            this.initChart('rating-genre-chart', {
                tooltip: { trigger: 'axis' },
                grid: { containLabel: true, left: '15%' },
                xAxis: { type: 'value', min: 2, max: 5, axisLabel: { color: '#fff' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } } },
                           yAxis: { type: 'category', data: genres.map(g => g[0]), axisLabel: { color: '#fff' } },
                           series: [{
                               type: 'bar', data: genres.map(g => g[1]),
                           itemStyle: { borderRadius: [0, 5, 5, 0], color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: '#7B68EE' }, { offset: 1, color: '#00F5FF' }]) }
                           }]
            });
        }
    };

    // ================= Part 5: 功能与事件 =================
    const Features = {

    };

    // ================= Part 5.5: 导出功能模块 (新增) =================
    const Export = {
        // 强制样式：确保截图时元素是可见的，且背景色正确
        config: {
            backgroundColor: '#0f0c29', // 对应 CSS 中的 --color-bg-1，防止背景透明
            pixelRatio: 2,              // 2倍图，保证文字清晰
            style: {
                opacity: '1',           // 强制不透明
                transform: 'none',      // 移除可能的位移动画
                animation: 'none',      // 停止动画
                transition: 'none'
            }
        },

        // 注入悬浮按钮
        initButton() {
            const btn = document.createElement('button');
            btn.innerText = '📸 批量导出所有图片';
            Object.assign(btn.style, {
                position: 'fixed', bottom: '30px', right: '30px', zIndex: '9999',
                padding: '12px 24px', background: 'linear-gradient(135deg, #00F5FF 0%, #7B68EE 100%)',
                border: 'none', color: '#fff', borderRadius: '30px',
                boxShadow: '0 4px 15px rgba(0, 245, 255, 0.4)',
                cursor: 'pointer', fontWeight: 'bold', fontSize: '14px',
                transition: 'all 0.3s'
            });
            
            btn.onmouseover = () => btn.style.transform = 'scale(1.05)';
            btn.onmouseout = () => btn.style.transform = 'scale(1)';
            
            // 点击事件：开始批量导出
            btn.onclick = async () => {
                btn.innerText = '⏳ 正在生成中...';
                btn.disabled = true;
                btn.style.opacity = '0.7';
                await this.exportAll();
                btn.innerText = '✅ 导出完成';
                setTimeout(() => {
                    btn.innerText = '📸 批量导出所有图片';
                    btn.disabled = false;
                    btn.style.opacity = '1';
                }, 3000);
            };
            
            document.body.appendChild(btn);
        },

        // 核心：批量处理
        async exportAll() {
            // 获取所有以 section-gshow_v 开头的节点
            const sections = document.querySelectorAll('div[id^="section-gshow_v"]');
            
            if (sections.length === 0) {
                alert("未找到可导出的章节");
                return;
            }

            for (let i = 0; i < sections.length; i++) {
                const node = sections[i];
                const fileName = `Report_Part_${i+1}_${node.id}.png`;
                
                try {
                    // 临时移除 .scroll-animate 类，防止截图时因为未滚动到该区域而导致透明
                    const originalClass = node.className;
                    // 强制所有子元素可见
                    const animates = node.querySelectorAll('.scroll-animate, .fade-in');
                    animates.forEach(el => el.style.opacity = '1');

                    // 生成图片
                    const dataUrl = await htmlToImage.toPng(node, this.config);
                    
                    // 下载
                    download(dataUrl, fileName);
                    console.log(`✅ 已导出: ${fileName}`);

                    // 恢复样式 (可选，如果导出后不刷新页面的话)
                    animates.forEach(el => el.style.opacity = '');

                    // 等待 800ms，避免浏览器瞬间负载过高导致崩溃或下载被拦截
                    await new Promise(r => setTimeout(r, 800));

                } catch (error) {
                    console.error(`❌ 导出 ${node.id} 失败:`, error);
                }
            }
        }
    };
    
    // ================= Part 6: 初始化流程 =================
    return {
        init(data) {
            console.log("🎬 ReportApp: 初始化...");

            // 1. 渲染 HTML
            document.getElementById('merged-content').innerHTML = Templates.generateAll(data);

            // 2. 渲染图表 (延迟一小会儿确保 DOM 就绪)
            setTimeout(() => {
                this.renderAllCharts(data);
                console.log("✅ 图表渲染完成");
                // 【新增】初始化导出按钮 (放在这里确保DOM已生成)
                Export.initButton();
            }, 100);

            // 3. 绑定事件
            this.bindEvents();

        },

        renderAllCharts(data) {
            Charts.initV2RatingPie(data);
            Charts.initV2GenrePie(data);
            Charts.initV2QuarterScatter(data);
            Charts.initV2MonthlyCount(data);
            Charts.initV2GenreBar(data);
            Charts.initV3DecadeChart(data);
            Charts.renderDirectorList(data);
            Charts.renderPersonList('top-actors-list', data['4_People_Analysis'].top_actors.slice(0, 20));
            Charts.renderPersonList('top-writers-list', data['4_People_Analysis'].top_writers.slice(0, 10));
            Charts.renderCloud('keyword-cloud', data['3_Content_Analysis'].intro_word_cloud.slice(0, 80));
            Charts.renderRareGenres(data);
            Charts.initV4RegionChart(data);
            Charts.initV4LanguageChart(data);
            Charts.initV5Calendar(data);
            Charts.initV6Map(data);
            Charts.initV7FiveStar(data);
            Charts.initV7MonthlyWords(data);
            Charts.renderCloud('comment-cloud', data['3_Content_Analysis'].comment_word_cloud?.slice(0, 80));
            Charts.renderRecommendations(data);
            Charts.initV9Charts(data);
        },

        bindEvents() {
            // 滚动动画
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) entry.target.classList.add('visible');
                });
            }, { threshold: 0.1 });

            setTimeout(() => {
                document.querySelectorAll('.scroll-animate, .fade-in').forEach(el => observer.observe(el));
            }, 200);

            // 窗口 Resize (使用防抖优化)
            window.addEventListener('resize', Utils.debounce(() => {
                Charts.instances.forEach(chart => chart.resize());
            }, 200));
        }
    };
})();

// 启动应用
document.addEventListener("DOMContentLoaded", () => {
    if (typeof REPORT_DATA !== 'undefined') {
        ReportApp.init(REPORT_DATA);
    } else {
        console.error("❌ REPORT_DATA 未定义，请检查 HTML 数据注入。");
    }
});
