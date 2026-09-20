class NewsFeeds:
    CATEGORIES = {
        
        # 1. CYBERSECURITY
        "cybersec": [
            "https://feeds.feedburner.com/TheHackersNews",
            "https://www.bleepingcomputer.com/feed/",
            "https://krebsonsecurity.com/feed/",
            "https://www.darkreading.com/rss.xml",
            "https://www.securityweek.com/rss"
        ],
        
        # 2. ARTIFICIAL INTELLIGENCE
        "ai": [
            "https://venturebeat.com/category/ai/feed/",
            "https://techcrunch.com/category/artificial-intelligence/feed/",
            "https://www.technologyreview.com/topic/artificial-intelligence/feed",
            "https://www.theverge.com/rss/artificial-intelligence/index.xml",
            "https://www.artificialintelligence-news.com/feed/",
            "https://www.marktechpost.com/feed/"
        ],
        
        # 3. SOFTWARE ENGINEERING & PROGRAMMING
        "programming": [
            "https://dev.to/feed",                                  
            "https://www.freecodecamp.org/news/rss/",               
            "https://www.infoworld.com/category/software-development/index.rss", 
            "https://sdtimes.com/feed/"                             
        ],
        
        # 4. ROBOTICS & AUTOMATION
        "robotics": [
            "https://therobotreport.com/feed/",                     
            "https://spectrum.ieee.org/feeds/topic/robotics.rss",   
            "https://robohub.org/feed/",                            
            "https://www.roboticsbusinessreview.com/feed/",
            "https://electronics.economictimes.indiatimes.com/rss/ai-robotics-automation"
        ],
        
        # 5. DEFENSE & AEROSPACE
        "defense_aerospace": [
            "https://breakingdefense.com/feed/",                    
            "https://www.defensenews.com/arc/outboundfeeds/rss/",   
            "https://spacenews.com/feed/",                          
            "https://www.space.com/feeds/all"                       
        ],
        
        # 6. SEMICONDUCTORS & HARDWARE
        "hardware": [
            "https://www.tomshardware.com/feeds/all",               
            "https://www.anandtech.com/rss",                        
            "https://spectrum.ieee.org/feeds/topic/semiconductors.rss", 
            "https://www.eejournal.com/feed/",
            "https://electronics.economictimes.indiatimes.com/rss/semiconductors",
            "https://electronics.economictimes.indiatimes.com/rss/components-hardware",
            "https://electronics.economictimes.indiatimes.com/rss/consumer-electronics",
            "https://electronics.economictimes.indiatimes.com/rss/manufacturing"
        ]
    }

    @classmethod
    def get_feeds(cls, category_name):
        """
        Returns the list of RSS URLs for a given category.
        Returns an empty list if the category doesn't exist.
        """
        return cls.CATEGORIES.get(category_name, [])