# First Prize RAG
环境配的有点乱，所以requirements.txt中环境写的不是很多，所以遇到了环境问题可以尝试补充道requirements.txt中

环境配置：pip install -r requirements.txt

ragmain是rag的主要框架parse_node.py & lightRAG_core.py & config.py是废案可以暂时不用管

现在已经完成了embedding，所以最终可以直接运行的是：终端执行python lightrag_query.py "你的问题"

需要注意的是我并没有把.env文件上传上来，因为包含我的apikey，运行的时候记得在ragmain文件夹下创建.env文件并填写：

LLAMA_CLOUD_API_KEY="你的apikey"

DASHSCOPE_API_KEY="或者我的apikey"

3.17

写了一个main.py入口，直接运行python main.py "你的问题" 就可以了（不需要再改ragmain的代码了）

现在md转pdf依赖wkhtmltopdf组件，这不是一个库，需要在电脑上安装一下

更新了requirements.txt多写了一些必要的库，有漏掉的话可以补充一下

需要在.env里面加上LR_WORKING_DIRS=rag_storage/civil_code,rag_storage/labor_law ，现在支持多库检索并合并输出
