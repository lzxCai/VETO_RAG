# from bs4 import BeautifulSoup
# import requests
# import os
# from datetime import datetime

# headers = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
# }

# # 创建输出文件夹
# output_dir = "markdown_pages"
# if not os.path.exists(output_dir):
#     os.makedirs(output_dir)

# # 创建索引文件
# index_filename = f"{output_dir}/README.md"
# with open(index_filename, 'w', encoding='utf-8') as index_file:
#     index_file.write("# 抓取页面索引\n\n")
#     index_file.write(f"**抓取页码范围：** 10300 - 10499\n\n")
#     index_file.write("| 页面ID | 标题 | 文件链接 |\n")
#     index_file.write("|--------|------|----------|\n")

# # 记录统计信息
# success_count = 0
# skip_count = 0
# fail_count = 0

# for page in range(10300, 10500):
#     try:
#         # 发送请求，设置超时和允许重定向
#         response = requests.get(
#             f"http://www.qmpfw.cn/index/article/show/article_id/{page}.html", 
#             headers=headers,
#             timeout=10,
#             allow_redirects=True
#         )
#         response.encoding = 'utf-8'
        
#         # 检查响应状态码
#         if response.status_code == 404:
#             skip_count += 1
#             continue
#         elif response.status_code != 200:
#             skip_count += 1
#             continue
        
#         html = response.text
#         soup = BeautifulSoup(html, "html.parser")
        
#         # 检查页面是否包含有效内容（可以根据实际情况调整判断条件）
#         all_title = soup.find_all("h1", attrs={"class": "content-title"})
#         all_strings = soup.find_all("div", attrs={"class": "col-xs-6 content-center"})
        
#         # 如果既没有标题也没有内容，则认为页面无效
#         if not all_title and not all_strings:

#             skip_count += 1
#             continue
        
#         # 提取标题作为文件名（如果没有标题则用页面ID）
#         title_text = ""
#         if all_title:
#             title_text = all_title[0].text.strip()
#             # 处理文件名中的非法字符
#             safe_title = "".join(c for c in title_text if c.isalnum() or c in (' ', '-', '_')).rstrip()
#             safe_title = safe_title[:50]  # 限制文件名长度
#         else:
#             safe_title = f"page_{page}"
        
#         # 生成文件名
#         md_filename = f"{output_dir}/{page}_{safe_title}.md"
        
#         with open(md_filename, 'w', encoding='utf-8') as md_file:
#             # 写入Markdown元数据
#             md_file.write("---\n")
#             md_file.write(f"page_id: {page}\n")
#             md_file.write(f"title: {title_text}\n")
#             md_file.write(f"crawled_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
#             md_file.write(f"url: http://www.qmpfw.cn/index/article/show/article_id/{page}.html\n")
#             md_file.write("---\n\n")
            
#             # 写入内容
#             for title in all_title:
#                 title_text_content = title.text.strip()
#                 md_file.write(f"# {title_text_content}\n\n")
#                 print(f"页面 {page} - 标题: {title_text_content}")
            
#             for string in all_strings:
#                 string_text = string.text.strip()
#                 # 处理内容格式
#                 string_text = string_text.replace('\n', '  \n')
#                 md_file.write(f"{string_text}\n\n")
#                 print(f"页面 {page} - 内容: {string_text[:50]}...")
        
#         # 更新索引文件
#         if all_title:
#             first_title = all_title[0].text.strip()[:30] + "..."
#         else:
#             first_title = "无标题"
        
#         with open(index_filename, 'a', encoding='utf-8') as index_file:
#             index_file.write(f"| {page} | {first_title} | [{page}_{safe_title}.md]({page}_{safe_title}.md) |\n")
        
#         success_count += 1
            
#     except requests.exceptions.Timeout:
#         print(f"页面 {page} 请求超时 - 已跳过")
#         skip_count += 1
#         continue
#     except requests.exceptions.ConnectionError:
#         print(f"页面 {page} 连接错误 - 已跳过")
#         skip_count += 1
#         continue
#     except requests.exceptions.RequestException as e:
#         print(f"页面 {page} 请求异常: {str(e)} - 已跳过")
#         skip_count += 1
#         continue
#     except Exception as e:
#         print(f"页面 {page} 处理失败: {str(e)}")
#         fail_count += 1
        
#         # 记录失败的页面
#         with open(f"{output_dir}/failed_pages.md", 'a', encoding='utf-8') as failed_file:
#             failed_file.write(f"- 页面 {page}: {str(e)}\n")

# # 在索引文件末尾添加统计信息
# with open(index_filename, 'a', encoding='utf-8') as index_file:
#     index_file.write("\n\n## 统计信息\n\n")
#     index_file.write(f"- 成功抓取：{success_count} 个页面\n")
#     index_file.write(f"- 跳过页面：{skip_count} 个页面\n")
#     index_file.write(f"- 失败页面：{fail_count} 个页面\n")
#     index_file.write(f"- 总计处理：{success_count + skip_count + fail_count} 个页面\n")

# print(f"\n抓取完成！")
# print(f"所有文件已保存至 {output_dir} 文件夹")
# print(f"索引文件：{index_filename}")
# print(f"统计信息：成功={success_count}, 跳过={skip_count}, 失败={fail_count}")

# from bs4 import BeautifulSoup
# import requests
# import time
# import os
# from urllib.parse import urljoin, urlparse
# from datetime import datetime

# headers = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
# }

# # 创建输出文件夹
# output_dir = "法治新闻_markdown"
# if not os.path.exists(output_dir):
#     os.makedirs(output_dir)

# # ===== 第一步：专门爬取带有 class="cimg mimg" 的图片 =====
# print("开始爬取图片（查找 class='cimg mimg' 的图片标签）...")
# image_urls = []  # 存储所有图片URL的列表

# # 爬取必应图片搜索的多页结果
# for page_num in range(1, 3):  # 爬取前2页
#     try:
#         # 必应图片搜索URL，first参数控制翻页
#         bing_url = f"https://cn.bing.com/images/search?q=法律图片&qpvt=法律图片&form=IQFRML&first={1 + (page_num - 1) * 36}"
#         print(f"\n正在爬取第 {page_num} 页: {bing_url}")

#         response = requests.get(bing_url, headers=headers, timeout=10)
#         response.encoding = 'utf-8'

#         if response.status_code == 200:
#             soup = BeautifulSoup(response.text, "html.parser")

#             # ===== 重点：查找所有同时包含 class="cimg" 和 class="mimg" 的图片 =====
#             target_images = soup.select("img.cimg.mimg")

#             page_image_count = 0
#             for img in target_images:
#                 # 获取图片URL（优先用src，如果没有则用data-src等属性）
#                 img_url = img.get("src") or img.get("data-src") or img.get("data-hi-res-url")

#                 if img_url:
#                     # 清理URL
#                     img_url = img_url.strip()

#                     # 确保是完整的HTTP URL
#                     if img_url.startswith("//"):
#                         img_url = "https:" + img_url
#                     elif img_url.startswith("/"):
#                         img_url = urljoin("https://cn.bing.com", img_url)

#                     # 过滤掉小的图标和base64图片
#                     if img_url.startswith("http") and not img_url.startswith("data:image"):
#                         if "w=276" in img_url or "&w=" in img_url:
#                             image_urls.append(img_url)
#                             page_image_count += 1
#                             print(f"  找到图片 [{page_image_count}]: {img_url[:80]}...")

#             print(f"第{page_num}页完成，本页找到 {page_image_count} 张目标图片，累计: {len(image_urls)}")

#             # 如果CSS选择器没找到，尝试用更宽松的条件
#             if page_image_count == 0:
#                 print("  使用备用查找方法...")
#                 all_imgs = soup.find_all("img")
#                 for img in all_imgs:
#                     img_class = img.get("class", [])
#                     if "cimg" in img_class or "mimg" in img_class:
#                         img_url = img.get("src") or img.get("data-src")
#                         if img_url and img_url.startswith("http"):
#                             image_urls.append(img_url)
#                             page_image_count += 1
#                             print(f"  备用方法找到: {img_url[:80]}...")

#             time.sleep(2)  # 页间延时
#         else:
#             print(f"请求失败，状态码: {response.status_code}")

#     except Exception as e:
#         print(f"爬取第{page_num}页图片时出错: {e}")
#         continue

# # 去重（保持顺序）
# seen = set()
# unique_image_urls = []
# for url in image_urls:
#     if url not in seen:
#         seen.add(url)
#         unique_image_urls.append(url)

# image_urls = unique_image_urls
# print(f"\n✅ 图片爬取完成！共找到 {len(image_urls)} 张带有 class='cimg mimg' 的不重复图片")

# if len(image_urls) > 0:
#     print("前5张图片预览:")
#     for i, url in enumerate(image_urls[:5]):
#         print(f"  {i + 1}. {url}")
# else:
#     print("⚠️ 没有找到任何目标图片，将使用占位符")
#     image_urls = [
#         "https://via.placeholder.com/800x600?text=Legal+Image+1",
#         "https://via.placeholder.com/800x600?text=Legal+Image+2",
#         "https://via.placeholder.com/800x600?text=Legal+Image+3"
#     ]

# # ===== 第二步：爬取文字，并循环匹配图片，保存为Markdown =====
# print("\n" + "=" * 60)
# print("开始爬取文章并保存为Markdown文件...")
# print("=" * 60)

# # 创建索引文件
# index_filename = f"{output_dir}/README.md"
# with open(index_filename, 'w', encoding='utf-8') as index_file:
#     index_file.write("# 法治新闻抓取索引\n\n")
#     index_file.write(f"**抓取时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
#     index_file.write(f"**图片来源：** 必应搜索“法律图片”\n\n")
#     index_file.write("| 文章ID | 标题 | 文件名 | 图片预览 |\n")
#     index_file.write("|--------|------|--------|----------|\n")

# # 图片索引计数器
# img_index = 0
# total_images = len(image_urls)
# success_count = 0
# skip_count = 0

# # 爬取文章
# for page in range(10300, 10320):
#     print(f"\n--- 正在处理文章ID: {page} ---")

#     try:
#         # 爬取文章
#         response = requests.get(f"http://www.qmpfw.cn/index/article/show/article_id/{page}.html", headers=headers, timeout=10)
#         response.encoding = 'utf-8'

#         if response.status_code != 200:
#             print(f"文章页面 {page} 无法访问，状态码: {response.status_code}")
#             skip_count += 1
#             continue

#         html = response.text
#         soup = BeautifulSoup(html, "html.parser")

#         all_title = soup.find_all("h1", attrs={"class": "content-title"})
#         all_strings = soup.find_all("div", attrs={"class": "col-xs-6 content-center"})

#         # 如果该页面没有内容，跳过
#         if not all_title and not all_strings:
#             print(f"页面 {page} 无内容，跳过")
#             skip_count += 1
#             continue

#         # 提取文章标题
#         article_title = ""
#         if all_title:
#             article_title = all_title[0].text.strip()
#         else:
#             article_title = f"无标题_{page}"

#         # 提取所有文章内容
#         article_content = []
#         for string in all_strings:
#             string_text = string.text.strip()
#             if string_text:  # 只添加非空内容
#                 article_content.append(string_text)

#         # ===== 获取匹配的图片 =====
#         current_img_url = image_urls[img_index % total_images]
#         img_index += 1

#         # ===== 生成安全的文件名 =====
#         # 移除文件名中的非法字符
#         safe_title = "".join(c for c in article_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
#         safe_title = safe_title[:50]  # 限制长度
#         if not safe_title:
#             safe_title = f"article_{page}"
        
#         # 生成文件名
#         filename = f"{page}_{safe_title}.md"
#         filepath = f"{output_dir}/{filename}"

#         # ===== 写入Markdown文件 =====
#         with open(filepath, 'w', encoding='utf-8') as md_file:
#             # 写入YAML frontmatter
#             md_file.write("---\n")
#             md_file.write(f"page_id: {page}\n")
#             md_file.write(f"title: {article_title}\n")
#             md_file.write(f"crawled_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
#             md_file.write(f"image_index: {img_index % total_images}\n")
#             md_file.write(f"image_url: {current_img_url}\n")
#             md_file.write("---\n\n")

#             # 写入文章标题
#             md_file.write(f"# {article_title}\n\n")

#             # 写入图片（Markdown格式）
#             md_file.write(f"![法律图片]({current_img_url})\n\n")
#             md_file.write(f"*图片来源：第{img_index % total_images + 1}张匹配图片*\n\n")
#             md_file.write("---\n\n")

#             # 写入文章内容
#             for i, content in enumerate(article_content, 1):
#                 md_file.write(f"## 段落 {i}\n\n")
#                 # 处理内容中的换行，转换为Markdown换行
#                 formatted_content = content.replace('\n', '  \n')
#                 md_file.write(f"{formatted_content}\n\n")
#                 if i < len(article_content):
#                     md_file.write("---\n\n")

            # 写入页脚
#             md_file.write("\n---\n")
#             md_file.write(f"*本文由爬虫自动生成，抓取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

#         # 更新索引文件
#         with open(index_filename, 'a', encoding='utf-8') as index_file:
#             # 截取标题前30个字符
#             display_title = (article_title[:30] + "...") if len(article_title) > 30 else article_title
#             # 生成图片预览的Markdown（小图）
#             img_preview = f"![img]({current_img_url})" if current_img_url else "无图片"
#             index_file.write(f"| {page} | {display_title} | [{filename}]({filename}) | ![预览]({current_img_url}) |\n")

#         success_count += 1
#         print(f"✅ 已保存: {filename}")
#         print(f"  标题: {article_title[:50]}...")
#         print(f"  图片: 第{img_index % total_images + 1}/{total_images}张")

#         time.sleep(1)  # 文章间延时

#     except Exception as e:
#         print(f"❌ 处理文章 {page} 时出错: {e}")
#         skip_count += 1
#         continue

# # ===== 第三步：生成汇总文件和统计信息 =====
# print("\n" + "=" * 60)
# print("📊 生成汇总文件...")

# # 生成目录文件
# with open(f"{output_dir}/SUMMARY.md", 'w', encoding='utf-8') as summary_file:
#     summary_file.write("# 文章目录\n\n")
#     summary_file.write(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
#     summary_file.write("## 文章列表\n\n")
    
#     # 列出所有生成的Markdown文件
#     md_files = [f for f in os.listdir(output_dir) if f.endswith('.md') and f != 'README.md' and f != 'SUMMARY.md']
#     md_files.sort()  # 按文件名排序
    
#     for md_file in md_files:
#         # 尝试读取文件标题
#         try:
#             with open(f"{output_dir}/{md_file}", 'r', encoding='utf-8') as f:
#                 content = f.read()
#                 # 简单提取第一行标题
#                 lines = content.split('\n')
#                 title_line = ""
#                 for line in lines:
#                     if line.startswith('# '):
#                         title_line = line[2:]
#                         break
#                 if not title_line:
#                     title_line = md_file
#         except:
#             title_line = md_file
        
#         summary_file.write(f"- [{title_line}]({md_file})\n")

# # 更新README.md添加统计信息
# with open(index_filename, 'a', encoding='utf-8') as index_file:
#     index_file.write("\n\n## 统计信息\n\n")
#     index_file.write(f"- ✅ 成功保存：**{success_count}** 篇文章\n")
#     index_file.write(f"- ⏭️ 跳过页面：**{skip_count}** 个\n")
#     index_file.write(f"- 🖼️ 图片来源：**{total_images}** 张图片（循环使用）\n")
#     index_file.write(f"- 📁 输出目录：`{output_dir}`\n")
#     index_file.write(f"- ⏰ 完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# print("\n" + "=" * 60)
# print("🎉 所有任务完成！")
# print(f"📁 输出目录: {output_dir}")
# print(f"📄 索引文件: {index_filename}")
# print(f"📄 目录文件: {output_dir}/SUMMARY.md")
# print("=" * 60)
# print(f"统计信息：")
# print(f"  ✅ 成功保存: {success_count} 篇文章")
# print(f"  ⏭️ 跳过页面: {skip_count} 个")
# print(f"  🖼️ 图片总数: {total_images} 张")
# print("=" * 60)

# from bs4 import BeautifulSoup
# import requests
# import time
# import os
# from urllib.parse import urljoin, urlparse
# from datetime import datetime

# headers = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
# }

# # 创建输出文件夹
# output_dir = "法治新闻_markdown"
# if not os.path.exists(output_dir):
#     os.makedirs(output_dir)

# # ===== 第一步：专门爬取带有 class="cimg mimg" 的图片 =====
# print("开始爬取图片（查找 class='cimg mimg' 的图片标签）...")
# image_urls = []  # 存储所有图片URL的列表

# # 爬取必应图片搜索的多页结果
# for page_num in range(1, 7):  # 爬取前6页
#     try:
#         # 必应图片搜索URL，first参数控制翻页
#         bing_url = f"https://cn.bing.com/images/search?q=法律图片&qpvt=法律图片&form=IQFRML&first={1 + (page_num - 1) * 36}"
#         print(f"\n正在爬取第 {page_num} 页: {bing_url}")

#         response = requests.get(bing_url, headers=headers, timeout=10)
#         response.encoding = 'utf-8'

#         if response.status_code == 200:
#             soup = BeautifulSoup(response.text, "html.parser")

#             # ===== 查找所有同时包含 class="cimg" 和 class="mimg" 的图片 =====
#             target_images = soup.select("img.cimg.mimg")

#             page_image_count = 0
#             for img in target_images:
#                 # 获取图片URL
#                 img_url = img.get("src") or img.get("data-src") or img.get("data-hi-res-url")

#                 if img_url:
#                     img_url = img_url.strip()

#                     # 确保是完整的HTTP URL
#                     if img_url.startswith("//"):
#                         img_url = "https:" + img_url
#                     elif img_url.startswith("/"):
#                         img_url = urljoin("https://cn.bing.com", img_url)

#                     # 过滤掉小的图标和base64图片
#                     if img_url.startswith("http") and not img_url.startswith("data:image"):
#                         if "w=276" in img_url or "&w=" in img_url:
#                             image_urls.append(img_url)
#                             page_image_count += 1
#                             print(f"  找到图片 [{page_image_count}]: {img_url[:80]}...")

#             print(f"第{page_num}页完成，本页找到 {page_image_count} 张目标图片，累计: {len(image_urls)}")

#             # 如果CSS选择器没找到，尝试用更宽松的条件
#             if page_image_count == 0:
#                 print("  使用备用查找方法...")
#                 all_imgs = soup.find_all("img")
#                 for img in all_imgs:
#                     img_class = img.get("class", [])
#                     if "cimg" in img_class or "mimg" in img_class:
#                         img_url = img.get("src") or img.get("data-src")
#                         if img_url and img_url.startswith("http"):
#                             image_urls.append(img_url)
#                             page_image_count += 1
#                             print(f"  备用方法找到: {img_url[:80]}...")

#             time.sleep(2)  # 页间延时
#         else:
#             print(f"请求失败，状态码: {response.status_code}")

#     except Exception as e:
#         print(f"爬取第{page_num}页图片时出错: {e}")
#         continue

# # 去重（保持顺序）
# seen = set()
# unique_image_urls = []
# for url in image_urls:
#     if url not in seen:
#         seen.add(url)
#         unique_image_urls.append(url)

# image_urls = unique_image_urls
# print(f"\n✅ 图片爬取完成！共找到 {len(image_urls)} 张带有 class='cimg mimg' 的不重复图片")

# if len(image_urls) > 0:
#     print("前5张图片预览:")
#     for i, url in enumerate(image_urls[:5]):
#         print(f"  {i + 1}. {url}")
# else:
#     print("⚠️ 没有找到任何目标图片，将使用占位符")
#     image_urls = [
#         "https://via.placeholder.com/800x600?text=Legal+Image+1",
#         "https://via.placeholder.com/800x600?text=Legal+Image+2",
#         "https://via.placeholder.com/800x600?text=Legal+Image+3"
#     ]

# # ===== 第二步：爬取文字（保留段落结构），并循环匹配图片，保存为Markdown =====
# print("\n" + "=" * 60)
# print("开始爬取文章（保留段落结构）并保存为Markdown文件...")
# print("=" * 60)

# # 创建索引文件
# index_filename = f"{output_dir}/README.md"
# with open(index_filename, 'w', encoding='utf-8') as index_file:
#     index_file.write("# 法治新闻抓取索引\n\n")
#     index_file.write(f"**抓取时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
#     index_file.write(f"**图片来源：** 必应搜索“法律图片”\n\n")
#     index_file.write("| 文章ID | 标题 | 文件名 | 图片预览 |\n")
#     index_file.write("|--------|------|--------|----------|\n")

# # 图片索引计数器
# img_index = 0
# total_images = len(image_urls)
# success_count = 0
# skip_count = 0

# # 爬取文章
# for page in range(10300, 105):
#     print(f"\n--- 正在处理文章ID: {page} ---")

#     try:
#         # 爬取文章
#         response = requests.get(f"http://www.qmpfw.cn/index/article/show/article_id/{page}.html", headers=headers, timeout=10)
#         response.encoding = 'utf-8'

#         if response.status_code != 200:
#             print(f"文章页面 {page} 无法访问，状态码: {response.status_code}")
#             skip_count += 1
#             continue

#         html = response.text
#         soup = BeautifulSoup(html, "html.parser")

#         # 提取标题
#         all_title = soup.find_all("h1", attrs={"class": "content-title"})
        
#         # ===== 关键修改：提取所有段落，保留结构 =====
#         # 方法1：如果内容在div.col-xs-6.content-center中，且内部有p标签
#         content_divs = soup.find_all("div", attrs={"class": "col-xs-6 content-center"})
        
#         paragraphs = []  # 存储所有段落
        
#         for content_div in content_divs:
#             # 查找div内的所有p标签
#             p_tags = content_div.find_all("p")
            
#             if p_tags:
#                 # 如果有p标签，提取每个p标签的文本作为独立段落
#                 for p in p_tags:
#                     p_text = p.text.strip()
#                     if p_text:  # 只添加非空段落
#                         paragraphs.append(p_text)
#                         print(f"  找到段落: {p_text[:50]}...")
#             else:
#                 # 如果没有p标签，将整个div内容作为一个段落
#                 div_text = content_div.text.strip()
#                 if div_text:
#                     # 尝试按换行符分割
#                     lines = [line.strip() for line in div_text.split('\n') if line.strip()]
#                     paragraphs.extend(lines)
#                     print(f"  找到内容块: {div_text[:50]}...")

#         # 如果仍然没有内容，尝试其他选择器
#         if not paragraphs:
#             # 尝试查找所有可能的内容标签
#             possible_content = soup.find_all(["p", "div", "span"], class_=lambda x: x and ("content" in x or "text" in x))
#             for elem in possible_content:
#                 text = elem.text.strip()
#                 if text and len(text) > 20:  # 只保留较长的文本
#                     paragraphs.append(text)
#                     print(f"  备用方法找到内容: {text[:50]}...")

#         # 如果该页面没有内容，跳过
#         if not all_title and not paragraphs:
#             print(f"页面 {page} 无内容，跳过")
#             skip_count += 1
#             continue

#         # 提取文章标题
#         article_title = ""
#         if all_title:
#             article_title = all_title[0].text.strip()
#         else:
#             article_title = f"无标题_{page}"

#         # ===== 获取匹配的图片 =====
#         current_img_url = image_urls[img_index % total_images]
#         img_index += 1

#         # ===== 生成安全的文件名 =====
#         safe_title = "".join(c for c in article_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
#         safe_title = safe_title[:50]
#         if not safe_title:
#             safe_title = f"article_{page}"
        
#         filename = f"{page}_{safe_title}.md"
#         filepath = f"{output_dir}/{filename}"

#         # ===== 写入Markdown文件（保留段落结构） =====
#         with open(filepath, 'w', encoding='utf-8') as md_file:
#             # 写入YAML frontmatter
#             md_file.write("---\n")
#             md_file.write(f"page_id: {page}\n")
#             md_file.write(f"title: {article_title}\n")
#             md_file.write(f"crawled_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
#             md_file.write(f"paragraph_count: {len(paragraphs)}\n")
#             md_file.write(f"image_index: {img_index % total_images}\n")
#             md_file.write(f"image_url: {current_img_url}\n")
#             md_file.write("---\n\n")

#             # 写入文章标题
#             md_file.write(f"# {article_title}\n\n")

#             # 写入图片（Markdown格式）
#             md_file.write(f"![法律图片]({current_img_url})\n\n")
#             md_file.write(f"*图片来源：第{img_index % total_images + 1}张匹配图片*\n\n")
#             md_file.write("---\n\n")

#             # ===== 写入文章内容，保留段落结构 =====
#             for i, paragraph in enumerate(paragraphs, 1):
#                 # 每个段落前可以加小标题（可选）
#                 # md_file.write(f"### 第{i}段\n\n")
                
#                 # 直接写入段落内容，每个段落之间用空行分隔
#                 md_file.write(f"{paragraph}\n\n")
                
#                 # 在段落之间添加分隔线（可选）
#                 if i < len(paragraphs):
#                     md_file.write("---\n\n")

#             # 写入页脚
#             md_file.write("\n---\n")
#             md_file.write(f"*本文由爬虫自动生成，包含 {len(paragraphs)} 个段落*\n\n")
#             md_file.write(f"*抓取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

#         # 更新索引文件
#         with open(index_filename, 'a', encoding='utf-8') as index_file:
#             display_title = (article_title[:30] + "...") if len(article_title) > 30 else article_title
#             index_file.write(f"| {page} | {display_title} | [{filename}]({filename}) | ![预览]({current_img_url}) |\n")

#         success_count += 1
#         print(f"✅ 已保存: {filename}")
#         print(f"  标题: {article_title[:50]}...")
#         print(f"  段落数: {len(paragraphs)}")
#         print(f"  图片: 第{img_index % total_images + 1}/{total_images}张")

#         time.sleep(1)  # 文章间延时

#     except Exception as e:
#         print(f"❌ 处理文章 {page} 时出错: {e}")
#         skip_count += 1
#         continue

# # ===== 第三步：生成汇总文件和统计信息 =====
# print("\n" + "=" * 60)
# print("📊 生成汇总文件...")

# # 生成目录文件
# with open(f"{output_dir}/SUMMARY.md", 'w', encoding='utf-8') as summary_file:
#     summary_file.write("# 文章目录\n\n")
#     summary_file.write(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
#     summary_file.write("## 文章列表\n\n")
    
#     md_files = [f for f in os.listdir(output_dir) if f.endswith('.md') and f != 'README.md' and f != 'SUMMARY.md']
#     md_files.sort()
    
#     for md_file in md_files:
#         try:
#             with open(f"{output_dir}/{md_file}", 'r', encoding='utf-8') as f:
#                 content = f.read()
#                 lines = content.split('\n')
#                 title_line = ""
#                 for line in lines:
#                     if line.startswith('# '):
#                         title_line = line[2:]
#                         break
#                 if not title_line:
#                     title_line = md_file
#         except:
#             title_line = md_file
        
#         summary_file.write(f"- [{title_line}]({md_file})\n")

# # 更新README.md添加统计信息
# with open(index_filename, 'a', encoding='utf-8') as index_file:
#     index_file.write("\n\n## 统计信息\n\n")
#     index_file.write(f"- ✅ 成功保存：**{success_count}** 篇文章\n")
#     index_file.write(f"- ⏭️ 跳过页面：**{skip_count}** 个\n")
#     index_file.write(f"- 🖼️ 图片来源：**{total_images}** 张图片（循环使用）\n")
#     index_file.write(f"- 📁 输出目录：`{output_dir}`\n")
#     index_file.write(f"- ⏰ 完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# print("\n" + "=" * 60)
# print("🎉 所有任务完成！")
# print(f"📁 输出目录: {output_dir}")
# print(f"📄 索引文件: {index_filename}")
# print(f"📄 目录文件: {output_dir}/SUMMARY.md")
# print("=" * 60)
# print(f"统计信息：")
# print(f"  ✅ 成功保存: {success_count} 篇文章")
# print(f"  ⏭️ 跳过页面: {skip_count} 个")
# print(f"  🖼️ 图片总数: {total_images} 张")
# print("=" * 60)

from bs4 import BeautifulSoup
import requests
import time
import os
import schedule
import json
import hashlib
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
}

# ===== 配置参数 =====
CONFIG = {
    "output_dir": "法治新闻_markdown",  # 输出目录
    "image_pages": 6,  # 图片爬取页数
    "article_start": 10300,  # 文章起始ID
    "article_end": 10500,  # 文章结束ID
    "schedule_hours": 6,  # 定时爬取间隔（小时）
    "enable_incremental": True,  # 是否启用增量爬取
    "max_retries": 3,  # 最大重试次数
    "request_timeout": 15,  # 请求超时时间
    "log_file": "crawler_log.txt"  # 日志文件
}

# ===== 日志记录函数 =====
def log_message(message, level="INFO"):
    """记录日志到文件和控制台"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry)
    
    with open(CONFIG["log_file"], "a", encoding="utf-8") as log_file:
        log_file.write(log_entry + "\n")

# ===== 状态管理 =====
class CrawlerState:
    """爬虫状态管理，用于增量爬取"""
    
    def __init__(self, state_file="crawler_state.json"):
        self.state_file = state_file
        self.state = self.load_state()
    
    def load_state(self):
        """加载状态文件"""
        default_state = self.get_default_state()
        
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    loaded_state = json.load(f)
                
                # 确保加载的状态包含所有默认键
                for key in default_state:
                    if key not in loaded_state:
                        loaded_state[key] = default_state[key]
                
                return loaded_state
            except:
                return default_state
        return default_state
    
    def get_default_state(self):
        """默认状态"""
        return {
            "last_run": None,
            "processed_articles": [],
            "processed_article_ids": [],
            "image_urls": [],
            "image_hash": None,  # 确保有这个键
            "total_articles": 0
        }
    
    def save_state(self):
        """保存状态"""
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
    
    def update_last_run(self):
        """更新最后运行时间"""
        self.state["last_run"] = datetime.now().isoformat()
    
    def add_processed_article(self, article_id, filename):
        """添加已处理的文章"""
        if article_id not in self.state["processed_article_ids"]:
            self.state["processed_article_ids"].append(article_id)
            self.state["processed_articles"].append({
                "id": article_id,
                "filename": filename,
                "time": datetime.now().isoformat()
            })
    
    def is_article_processed(self, article_id):
        """检查文章是否已处理"""
        return article_id in self.state["processed_article_ids"]
    
    def update_image_urls(self, image_urls):
        """更新图片URL列表"""
        # 计算图片列表的哈希值，用于检测变化
        image_str = "".join(sorted(image_urls))
        new_hash = hashlib.md5(image_str.encode()).hexdigest()
        
        # 安全地获取 image_hash，如果不存在则设为 None
        current_hash = self.state.get("image_hash")
        
        if current_hash != new_hash:
            self.state["image_urls"] = image_urls
            self.state["image_hash"] = new_hash
            return True  # 图片有变化
        return False  # 图片无变化
    

# ===== 图片爬取函数 =====
def crawl_images():
    """爬取图片"""
    log_message("开始爬取图片...")
    image_urls = []
    
    for page_num in range(1, CONFIG["image_pages"] + 1):
        for retry in range(CONFIG["max_retries"]):
            try:
                bing_url = f"https://cn.bing.com/images/search?q=法律图片&qpvt=法律图片&form=IQFRML&first={1 + (page_num - 1) * 36}"
                log_message(f"正在爬取第 {page_num} 页 (尝试 {retry + 1}/{CONFIG['max_retries']})")
                
                response = requests.get(bing_url, headers=headers, timeout=CONFIG["request_timeout"])
                response.encoding = 'utf-8'
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    target_images = soup.select("img.cimg.mimg")
                    
                    page_image_count = 0
                    for img in target_images:
                        img_url = img.get("src") or img.get("data-src") or img.get("data-hi-res-url")
                        
                        if img_url:
                            img_url = img_url.strip()
                            
                            if img_url.startswith("//"):
                                img_url = "https:" + img_url
                            elif img_url.startswith("/"):
                                img_url = urljoin("https://cn.bing.com", img_url)
                            
                            if img_url.startswith("http") and not img_url.startswith("data:image"):
                                if "w=276" in img_url or "&w=" in img_url:
                                    image_urls.append(img_url)
                                    page_image_count += 1
                    
                    log_message(f"第{page_num}页完成，找到 {page_image_count} 张图片，累计: {len(image_urls)}")
                    
                    # 如果没找到图片，尝试备用方法
                    if page_image_count == 0:
                        all_imgs = soup.find_all("img")
                        for img in all_imgs:
                            img_class = img.get("class", [])
                            if "cimg" in img_class or "mimg" in img_class:
                                img_url = img.get("src") or img.get("data-src")
                                if img_url and img_url.startswith("http"):
                                    image_urls.append(img_url)
                                    page_image_count += 1
                        
                        if page_image_count > 0:
                            log_message(f"备用方法找到 {page_image_count} 张图片")
                    
                    break  # 成功则跳出重试循环
                else:
                    log_message(f"请求失败，状态码: {response.status_code}", "WARNING")
                    
            except Exception as e:
                log_message(f"爬取第{page_num}页图片时出错: {e}", "ERROR")
                if retry < CONFIG["max_retries"] - 1:
                    time.sleep(5)  # 重试前等待
                else:
                    log_message(f"第{page_num}页重试失败，跳过", "ERROR")
        
        time.sleep(2)  # 页间延时
    
    # 去重
    seen = set()
    unique_image_urls = []
    for url in image_urls:
        if url not in seen:
            seen.add(url)
            unique_image_urls.append(url)
    
    image_urls = unique_image_urls
    log_message(f"图片爬取完成！共找到 {len(image_urls)} 张不重复图片")
    
    # 如果没有图片，使用占位符
    if len(image_urls) == 0:
        log_message("没有找到任何图片，使用占位符", "WARNING")
        image_urls = [
            "https://via.placeholder.com/800x600?text=Legal+Image+1",
            "https://via.placeholder.com/800x600?text=Legal+Image+2",
            "https://via.placeholder.com/800x600?text=Legal+Image+3"
        ]
    
    return image_urls

# ===== 文章爬取函数 =====
def crawl_articles(image_urls, crawler_state):
    """爬取文章"""
    log_message("开始爬取文章...")
    
    total_images = len(image_urls)
    success_count = 0
    skip_count = 0
    
    # 创建索引文件（如果不存在）
    index_filename = f"{CONFIG['output_dir']}/README.md"
    if not os.path.exists(index_filename):
        with open(index_filename, 'w', encoding='utf-8') as index_file:
            index_file.write("# 法治新闻抓取索引\n\n")
            index_file.write(f"**首次抓取时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            index_file.write(f"**图片来源：** 必应搜索“法律图片”\n\n")
            index_file.write("| 文章ID | 标题 | 文件名 | 图片预览 | 抓取时间 |\n")
            index_file.write("|--------|------|--------|----------|----------|\n")
    
    # 图片索引计数器
    img_index = len(crawler_state.state["processed_articles"]) % total_images if total_images > 0 else 0
    
    for page in range(CONFIG["article_start"], CONFIG["article_end"] + 1):
        # 如果启用增量爬取且文章已处理，则跳过
        if CONFIG["enable_incremental"] and crawler_state.is_article_processed(page):
            log_message(f"文章ID {page} 已处理，跳过")
            skip_count += 1
            continue
        
        log_message(f"正在处理文章ID: {page}")
        
        for retry in range(CONFIG["max_retries"]):
            try:
                response = requests.get(
                    f"http://www.qmpfw.cn/index/article/show/article_id/{page}.html", 
                    headers=headers, 
                    timeout=CONFIG["request_timeout"]
                )
                response.encoding = 'utf-8'
                
                if response.status_code != 200:
                    log_message(f"文章页面 {page} 无法访问，状态码: {response.status_code}", "WARNING")
                    if retry < CONFIG["max_retries"] - 1:
                        time.sleep(3)
                        continue
                    else:
                        skip_count += 1
                        break
                
                html = response.text
                soup = BeautifulSoup(html, "html.parser")
                
                all_title = soup.find_all("h1", attrs={"class": "content-title"})
                
                content_divs = soup.find_all("div", attrs={"class": "col-xs-6 content-center"})
                paragraphs = []
                
                for content_div in content_divs:
                    p_tags = content_div.find_all("p")
                    
                    if p_tags:
                        for p in p_tags:
                            p_text = p.text.strip()
                            if p_text:
                                paragraphs.append(p_text)
                    else:
                        div_text = content_div.text.strip()
                        if div_text:
                            lines = [line.strip() for line in div_text.split('\n') if line.strip()]
                            paragraphs.extend(lines)
                
                if not paragraphs:
                    possible_content = soup.find_all(["p", "div", "span"], 
                                                     class_=lambda x: x and ("content" in x or "text" in x))
                    for elem in possible_content:
                        text = elem.text.strip()
                        if text and len(text) > 20:
                            paragraphs.append(text)
                
                if not all_title and not paragraphs:
                    log_message(f"页面 {page} 无内容，跳过")
                    skip_count += 1
                    break
                
                article_title = ""
                if all_title:
                    article_title = all_title[0].text.strip()
                else:
                    article_title = f"无标题_{page}"
                
                current_img_url = image_urls[img_index % total_images]
                img_index += 1
                
                safe_title = "".join(c for c in article_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = safe_title[:50]
                if not safe_title:
                    safe_title = f"article_{page}"
                
                filename = f"{page}_{safe_title}.md"
                filepath = f"{CONFIG['output_dir']}/{filename}"
                
                # 写入Markdown文件
                with open(filepath, 'w', encoding='utf-8') as md_file:
                    # YAML frontmatter
                    md_file.write("---\n")
                    md_file.write(f"page_id: {page}\n")
                    md_file.write(f"title: {article_title}\n")
                    md_file.write(f"crawled_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    md_file.write(f"paragraph_count: {len(paragraphs)}\n")
                    md_file.write(f"image_index: {img_index % total_images}\n")
                    md_file.write(f"image_url: {current_img_url}\n")
                    md_file.write("---\n\n")
                    
                    md_file.write(f"# {article_title}\n\n")
                    md_file.write(f"![法律图片]({current_img_url})\n\n")
                    md_file.write(f"*图片来源：第{img_index % total_images + 1}张匹配图片*\n\n")
                    md_file.write("---\n\n")
                    
                    for i, paragraph in enumerate(paragraphs, 1):
                        md_file.write(f"{paragraph}\n\n")
                        if i < len(paragraphs):
                            md_file.write("---\n\n")
                    
                    md_file.write("\n---\n")
                    md_file.write(f"*本文由爬虫自动生成，包含 {len(paragraphs)} 个段落*\n\n")
                    md_file.write(f"*抓取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
                
                with open(index_filename, 'a', encoding='utf-8') as index_file:
                    display_title = (article_title[:30] + "...") if len(article_title) > 30 else article_title
                    index_file.write(f"| {page} | {display_title} | [{filename}]({filename}) | ![预览]({current_img_url}) | {datetime.now().strftime('%Y-%m-%d %H:%M')} |\n")
                
                crawler_state.add_processed_article(page, filename)
                
                success_count += 1
                log_message(f"✅ 已保存: {filename} (段落数: {len(paragraphs)})")
                
                time.sleep(1)  # 文章间延时
                break  # 成功则跳出重试循环
                
            except Exception as e:
                log_message(f"处理文章 {page} 时出错: {e}", "ERROR")
                if retry < CONFIG["max_retries"] - 1:
                    time.sleep(5)
                else:
                    skip_count += 1
                    log_message(f"文章 {page} 重试失败，跳过", "ERROR")
    
    return success_count, skip_count

# ===== 主爬虫函数 =====
def run_crawler():
    """运行完整爬虫"""
    log_message("=" * 60)
    log_message("爬虫任务开始")
    log_message("=" * 60)
    
    if not os.path.exists(CONFIG["output_dir"]):
        os.makedirs(CONFIG["output_dir"])
    
    crawler_state = CrawlerState()
    
    image_urls = crawl_images()
    image_changed = crawler_state.update_image_urls(image_urls)
    
    if image_changed:
        log_message("图片列表已更新")
    
    success, skip = crawl_articles(image_urls, crawler_state)
    
    crawler_state.update_last_run()
    crawler_state.state["total_articles"] = success
    crawler_state.save_state()
    
    generate_summary()
    
    log_message("=" * 60)
    log_message(f"爬虫任务完成！成功: {success} 篇, 跳过: {skip} 篇")
    log_message("=" * 60)
    
    return success, skip

# ===== 生成汇总文件 =====
def generate_summary():
    """生成汇总目录文件"""
    summary_file = f"{CONFIG['output_dir']}/SUMMARY.md"
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("# 文章目录\n\n")
        f.write(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## 文章列表\n\n")
        
        md_files = [f for f in os.listdir(CONFIG['output_dir']) 
                   if f.endswith('.md') and f not in ['README.md', 'SUMMARY.md']]
        md_files.sort()
        
        for md_file in md_files:
            try:
                with open(f"{CONFIG['output_dir']}/{md_file}", 'r', encoding='utf-8') as f2:
                    content = f2.read()
                    lines = content.split('\n')
                    title_line = ""
                    for line in lines:
                        if line.startswith('# '):
                            title_line = line[2:]
                            break
                    if not title_line:
                        title_line = md_file
            except:
                title_line = md_file
            
            f.write(f"- [{title_line}]({md_file})\n")

# ===== 定时任务 =====
def scheduled_job():
    """定时执行的爬虫任务"""
    log_message("定时爬虫任务触发")
    try:
        run_crawler()
    except Exception as e:
        log_message(f"定时任务执行失败: {e}", "ERROR")

# ===== 主程序 =====
import argparse

if __name__ == "__main__":
    import sys

    # 如果带参数运行，跳过交互菜单，直接走 argparse
    if len(sys.argv) == 1:
        print("=" * 60)
        print("法治新闻爬虫")
        print("=" * 60)
        print("请选择运行模式：")
        print("1. 立即运行一次")
        print(f"2. 定时运行（每{CONFIG['schedule_hours']}小时执行一次）")
        print("3. 查看状态")
        print("4. 退出")
        print("=" * 60)

        choice = input("请输入选择 (1-4): ").strip()

        if choice == "1":
            run_crawler()
        elif choice == "2":
            log_message(f"定时爬虫已启动，每{CONFIG['schedule_hours']}小时执行一次")
            log_message("按 Ctrl+C 停止")
            run_crawler()
            schedule.every(CONFIG["schedule_hours"]).hours.do(scheduled_job)
            try:
                while True:
                    schedule.run_pending()
                    time.sleep(60)
            except KeyboardInterrupt:
                log_message("定时爬虫已停止")
        elif choice == "3":
            crawler_state = CrawlerState()
            print("\n" + "=" * 60)
            print("爬虫状态")
            print("=" * 60)
            print(f"最后运行时间: {crawler_state.state['last_run'] or '从未运行'}")
            print(f"已处理文章数: {len(crawler_state.state['processed_articles'])}")
            print(f"图片数量: {len(crawler_state.state['image_urls'])}")
            print(f"图片哈希: {crawler_state.state['image_hash']}")
            print("\n最近5篇处理的文章:")
            for article in crawler_state.state['processed_articles'][-5:]:
                print(f"  - {article['id']}: {article['filename']} ({article['time'][:16]})")
            print("=" * 60)
        else:
            print("退出程序")
            raise SystemExit(0)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="法治新闻爬虫")
    parser.add_argument("--mode", choices=["once", "schedule", "status"], default="once",
                       help="运行模式: once(一次), schedule(定时), status(状态)")
    parser.add_argument("--start", type=int, help="文章起始ID")
    parser.add_argument("--end", type=int, help="文章结束ID")
    parser.add_argument("--hours", type=int, help="定时运行间隔(小时)")
    return parser.parse_args()

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        args = parse_args()

        if args.start:
            CONFIG["article_start"] = args.start
        if args.end:
            CONFIG["article_end"] = args.end
        if args.hours:
            CONFIG["schedule_hours"] = args.hours

        if args.mode == "once":
            run_crawler()
        elif args.mode == "schedule":
            log_message(f"定时爬虫启动，每{CONFIG['schedule_hours']}小时执行一次")
            schedule.every(CONFIG["schedule_hours"]).hours.do(scheduled_job)
            try:
                while True:
                    schedule.run_pending()
                    time.sleep(60)
            except KeyboardInterrupt:
                log_message("定时爬虫已停止")
        elif args.mode == "status":
            crawler_state = CrawlerState()
            print(json.dumps(crawler_state.state, ensure_ascii=False, indent=2))