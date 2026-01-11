saveMoviesPages         存储已看电影数据页                                                                   得到htmls
Raw2Detail              基本刮削                    中文名、外文名、豆瓣链接、我的打分、评论、                     得到douban_movies.csv
KeywordMaintenance      维护本地关键词库
KeywordClassify         利用本地关键词库进行精细刮削      地区、语言、人物、类型                                   得到douban_movies_classified.csv
Tmdb                    tmdbapi下载海报，              本地海报路径                                           得到douban_movies_enhanced.csv
CTsv_Col_Rm             删除静态数据库中没用的列，并保存到原来的位置（替换原文件）
MergeEnrichedMovies     合并丰富的数据库
import_csv_to_sqlite    导入到sqlite数据库


豆瓣
静态数据集来源于kanggle
