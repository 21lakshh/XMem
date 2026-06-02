<div align="center">
  <img
    src="https://github.com/user-attachments/assets/aa171a4c-074c-4082-b3d1-c70f5f7f2aca"
    alt="XMem Logo"
    width="100%"
  />
</div>

<div align="center">
  <h1>XMem</h1>
  <p><strong>AI के लिए मेमोरी लेयर जो कभी भूलती नहीं है</strong></p>
  <p>हर AI एजेंट और LLM इंटरफेस को तुरंत स्थायी, क्रॉस-प्लेटफॉर्म मेमोरी दें।</p>


<img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python 3.11+"/>
<img src="https://img.shields.io/badge/license-BSD--3--Clause-green" alt="BSD-3 License"/>
<img src="https://img.shields.io/badge/FastAPI-00C7B7?logo=fastapi&logoColor=white" alt="FastAPI"/>
<br/>
<img src="https://img.shields.io/badge/LangGraph-6C47FF?logo=langchain&logoColor=white" alt="LangGraph"/>
<img src="https://img.shields.io/badge/Rust-Weaver-b7410e?logo=rust&logoColor=white" alt="Rust Weaver"/>
<img src="https://img.shields.io/badge/Multi--LLM-Gemini%20%7C%20Claude%20%7C%20GPT%20%7C%20Bedrock%20%7C%20Ollama-orange" alt="Multi-LLM"/>
</div>

<hr>

<p align="center">
  <a href="README.md">English</a> &nbsp;&bull;&nbsp;
  <a href="README.zh-CN.md">简体中文</a> &nbsp;&bull;&nbsp;
  <a href="README.ja.md">日本語</a> &nbsp;&bull;&nbsp;
  <a href="README.hi.md">हिन्दी</a>
</p>

<p align="center">
  <a href="#डेमो">डेमो</a> &nbsp;&bull;&nbsp;
  <a href="#विशेषताएं">विशेषताएं</a> &nbsp;&bull;&nbsp;
  <a href="#आर्किटेक्चर">आर्किटेक्चर</a> &nbsp;&bull;&nbsp;
  <a href="#बेंचमार्क">बेंचमार्क</a> &nbsp;&bull;&nbsp;
  <a href="#त्वरित-शुरुआत">त्वरित शुरुआत</a> &nbsp;&bull;&nbsp;
  <a href="#कॉन्फ़िगरेशन">कॉन्फ़िगरेशन</a>
</p>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=XortexAI/XMem&type=date&theme=dark&legend=top-left" />
  <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=XortexAI/XMem&type=date&legend=top-left" />
  <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=XortexAI/XMem&type=date&legend=top-left" />
</picture>

## अपडेट / समाचार
- **[1 जून 2026]** XMem के पास अब इसकी मेमोरी लेयर का नेटिव Golang कार्यान्वयन है। उच्च थ्रूपुट, कम विलंबता, और उत्पादन-स्तरीय परिनियोजन के लिए बनाया गया है जहां मेमोरी को लाखों इंटरैक्शन में विश्वसनीयता से काम करना होता है।
- **[25 मई 2026]** स्थानीय वर्कस्पेस समर्थन अब लाइव है। XMem को मात्र 3 कमांड में स्थानीय रूप से सेट अप करें और मिनटों में मेमोरी के साथ निर्माण करना शुरू करें। सेटअप निर्देशों के लिए [Local.md](https://github.com/XortexAI/XMem/blob/main/Local.md) देखें।
 ```bash
npx create-xmem@latest
cd xmem
npm run dev
```


## XMem क्या है?

LLM के साथ हर बातचीत शून्य से शुरू होती है। टूल स्विच करें, प्रदाता स्विच करें, अगले सप्ताह वापस आएं और सारा संदर्भ गायब है।

XMem भारत की #1 ओपन सोर्स एजेंटिक मेमोरी लेयर है, हम मेमोरी-ऐज़-ए-सर्विस पेश कर रहे हैं, यानी हर AI उपयोग के मामले, डोमेन के लिए मेमोरी लेयर, चाहे वह लंबे समय तक चलने वाले एजेंटों के लिए समय-आधारित मेमोरी हो, रोगी संदर्भ के लिए चिकित्सा मेमोरी हो, टीमों और परियोजनाओं के लिए एंटरप्राइज मेमोरी हो, या कोडिंग एजेंटों और वर्कफ़्लो के लिए डेवलपर मेमोरी हो।

यह स्टेटफुल AI के लिए एक अनूठी किस्म की एजेंटिक मेमोरी लेयर है।
पारंपरिक मेमोरी सिस्टम के विपरीत जो केवल चंक संग्रहीत और पुनः प्राप्त करते हैं, XMem मेमोरी को एक सक्रिय तर्क प्रक्रिया में बदल देता है। यह निर्णय लेता है कि क्या याद रखना है, क्या अपडेट करना है, क्या भूलना है, और प्रत्येक मेमोरी को सही विशेषज्ञ एजेंट और स्टोर में गतिशील रूप से रूट करता है।

## डेमो

किसी भी AI प्लेटफॉर्म पर "X" टाइप करें और अपनी मेमोरी को निर्बाध रूप से संग्रहीत और खोजने, मौजूदा चैट से संदर्भ आयात करने, या अनुक्रमित रिपो के साथ काम करने के लिए XMem द्वारा दी जाने वाली चार मोड के बीच चयन करें।

https://github.com/user-attachments/assets/8e3349ab-63c9-4046-821d-ca8097948440

## विशेषताएं

### Chrome एक्सटेंशन

XMem Chrome एक्सटेंशन ChatGPT, Claude, Gemini, DeepSeek, और Perplexity को स्थायी मेमोरी लाता है।

**लाइव सर्च और इंजेक्ट** - जैसे ही आप प्रॉम्प्ट टाइप करते हैं, XMem रीयल-टाइम में आपकी मेमोरी को खोजता है और एक फ्लोटिंग चिप दिखाता है। एक क्लिक सीधे आपके इनपुट में प्रासंगिक संदर्भ इंजेक्ट करता है, कोई घर्षण नहीं।

**पृष्ठभूमि ऑटो-सेव (Xingest)** - जब आप "भेजें" दबाते हैं, XMem अनिवार्य रूप से बातचीत मोड़ को कैप्चर करता है। एक पृष्ठभूमि कतार आपके UI को छुए बिना तथ्यों और सारांशों को निकालता है।

https://github.com/user-attachments/assets/97793cf9-d247-4d02-9c31-3cc9bbbf89aa

### एजेंट प्लगइन

इसमें [Claude Code](plugin/xmem-claude/), [Codex](plugin/xmem-codex/), [Cursor](plugin/xmem-cursor/), [Hermes](plugin/xmem-hermes/), [OpenClaw](plugin/xmem-openclaw/) और [OpenCode](plugin/xmem-opencode/) के लिए प्रथम-पक्षीय एकीकरण शामिल हैं, ताकि एजेंट मौजूदा मेमोरी खोज सकें, टिकाऊ परियोजना ज्ञान सहेज सकें, और सत्रों के बीच संदर्भ ले जा सकें जबकि API कुंजियों को पर्यावरण चर या क्लाइंट-विशिष्ट गुप्त स्टोर में रखते हैं।

### संदर्भ

संदर्भ आपको किसी भी चीज़ को मैन्युअल रूप से कॉपी पेस्ट किए बिना एक मौजूदा बातचीत को XMem में लाने देता है।

साझा किया गया ChatGPT, Claude, या Gemini लिंक पेस्ट करें। XMem इसे खोलता है, हर उपयोगकर्ता और सहायक संदेश निकालता है, और पूरी इनगेशन पाइपलाइन चलाता है ताकि बातचीत खोज योग्य मेमोरी बन जाए।

आप एक ट्रांसक्रिप्ट फ़ाइल (पाठ, मार्कडाउन, या JSON) भी अपलोड कर सकते हैं। XMem के पास Cursor और Antigravity निर्यात के लिए निर्मित पार्सिंग है और अज्ञात प्रारूपों के लिए एक LLM फॉलबैक का उपयोग करता है।

https://github.com/user-attachments/assets/4ff22405-b7ad-4b78-9189-9a6e3ebd5e40

### स्कैनर

स्कैनर संपूर्ण Git रिपोजिटरीज को अनुक्रमित करता है और आपके कोडबेस का एक क्वेरीयोग्य ज्ञान ग्राफ बनाता है।

एक बार अनुक्रमित होने के बाद, आप फ़ाइलों, कार्यों, निर्भरताओं, और प्रभाव के बारे में प्राकृतिक भाषा प्रश्न पूछ सकते हैं। इसका उपयोग एक नई रिपो को समझने, यह पता लगाने के लिए करें कि कोई सुविधा कहां रहती है, ट्रेस करें कि कोड कैसे जुड़ता है, या यह समझें कि आप कुछ बदलने से क्या टूट जाएगा।

https://github.com/user-attachments/assets/f0fd393e-3820-404b-8d0e-e452e1dd52d0

### बहु-डोमेन वर्गीकरण

सभी मेमोरी समान नहीं है, और इसके साथ इसे उसी तरह व्यवहार करना अन्य समाधानों को कम प्रदर्शन करता है। XMem का **Classifier Agent** आने वाले प्रत्येक डेटा को विश्लेषण करता है और इसे सही डोमेन में रूट करता है:

<table>
  <tr>
    <th>डोमेन</th>
    <th>यह क्या संग्रहीत करता है</th>
    <th>उदाहरण</th>
    <th>भंडारण</th>
  </tr>
  <tr>
    <td><strong>प्रोफाइल</strong></td>
    <td>स्थायी उपयोगकर्ता तथ्य, प्राथमिकताएं, पहचान</td>
    <td><em>"मुझे backends के लिए Go, Python से ज्यादा पसंद है"</em></td>
    <td>Pinecone</td>
  </tr>
  <tr>
    <td><strong>अस्थायी</strong></td>
    <td>समय-लंगर घटनाएं तारीख संकल्प के साथ</td>
    <td><em>"मुझे कल Staff Engineer के रूप में पदोन्नति मिली"</em></td>
    <td>Neo4j</td>
  </tr>
  <tr>
    <td><strong>सारांश</strong></td>
    <td>संपीड़ित बातचीत सारांश</td>
    <td><em>"REST से gRPC में माइग्रेशन पर चर्चा की गई"</em></td>
    <td>Pinecone</td>
  </tr>
  <tr>
    <td><strong>कोड</strong></td>
    <td>प्रतीकों से जुड़ी व्याख्याएं, बग, व्याख्याएं</td>
    <td><em>"इस रीट्राई लॉजिक में एक रेस कंडीशन है"</em></td>
    <td>Neo4j + Pinecone</td>
  </tr>
  <tr>
    <td><strong>स्निपेट</strong></td>
    <td>व्यक्तिगत कोड पैटर्न और उपयोगिता</td>
    <td><em>"यह Go में मेरा मानक त्रुटि हैंडलर है"</em></td>
    <td>Pinecone</td>
  </tr>
  <tr>
    <td><strong>छवि</strong></td>
    <td>दृश्य अवलोकन और विवरण</td>
    <td><em>आर्किटेक्चर आरेख का स्क्रीनशॉट</em></td>
    <td>Pinecone</td>
  </tr>
</table>

### एजेंटिक रिट्रीवल

जब आप XMem को क्वेरी करते हैं, तो रिट्रीवल एक सरल वेक्टर सर्च नहीं है। LLM स्वयं निर्णय लेता है कि क्या *खोजना है*:

1. **टूल चयन** - रिट्रीवल LLM आपकी क्वेरी का विश्लेषण करता है और उपयुक्त सर्च टूल (SearchProfile, SearchTemporal, SearchSummary, SearchSnippet) को कॉल करता है, संभावित रूप से समानांतर में कई।
2. **संश्लेषण** - सभी सर्च टूल के परिणाम एकत्र किए जाते हैं और LLM स्रोत संदर्भों के साथ एक उद्धृत उत्तर उत्पन्न करता है।

इसका अर्थ है *"मेरी पसंदीदा टेक स्टैक क्या है और मैंने अंतिम बार auth मॉड्यूल को रीफैक्टर कब किया?"* पूछना स्वचालित रूप से प्रोफाइल लुकअप और एक अस्थायी सर्च दोनों को ट्रिगर करता है।

### Multi-LLM ऑर्केस्ट्रेशन फॉलबैक के साथ

XMem एक प्रदाता पर बंद नहीं है। यह **Gemini, Claude, OpenAI, OpenRouter, Amazon Bedrock, और Ollama** में ऑर्केस्ट्रेट करता है स्वचालित फॉलबैक के साथ:

```
gemini -> claude -> openai -> bedrock -> ollama
```

यदि आपका प्राथमिक LLM दर सीमित करता है या नीचे चला जाता है, XMem चुपचाप अगले प्रदाता को फॉलबैक करता है। प्रत्येक एजेंट एक विशिष्ट मॉडल पर पिन किया जा सकता है। फॉलबैक क्रम पूरी तरह से कॉन्फ़िगर करने योग्य है।

### स्थानीय रूप से चलाता है

कोई क्लाउड निर्भरता आवश्यक नहीं है। Ollama के साथ XMem चलाएं LLM के लिए, FastEmbed एम्बेडिंग के लिए, और Chroma या SQLite वेक्टर स्टोरेज के लिए:

```bash
pip install -e ".[local]"
```

## आर्किटेक्चर

<img width="1536" height="1024" alt="WhatsApp Image 2026-04-27 at 11 50 51" src="https://github.com/user-attachments/assets/424d1c77-63e3-48ac-b457-6beecd437f65" />

XMem को **विशेषज्ञ AI एजेंटों की पाइपलाइन** के रूप में बनाया गया है जो LangGraph द्वारा समन्वित है, निर्धारणीय निष्पादन लेयर (Weaver) और तीन उद्देश्य-निर्मित संग्रहण इंजन द्वारा समर्थित है।

### इनगेशन फ्लो

```
यूजर इनपुट (SDK / Chrome Extension / API)
         |
         v
   +--------------+
   |  Classifier   |    पाठ का विश्लेषण करता है, डोमेन में रूट करता है
   +------+-------+
          |
    +-----+-----+------+----------+
    v     v     v      v          v
 Profile Temporal Summary Code  Snippet     डोमेन एजेंट निकालते हैं
 Agent   Agent   Agent  Agent   Agent       संरचित डेटा समानांतर में
    |     |      |      |        |
    v     v      v      v        v
   +----------------------------------+
   |          Judge Agent             |     मौजूदा मेमोरी के विरुद्ध तुलना करता है
   |   (ADD / UPDATE / DELETE / NOOP) |     डुप्लिकेट और स्टेलनेस को रोकता है
   +----------------+-----------------+
                    |
                    v
   +----------------------------------+
   |        Weaver (Rust core)        |     निर्धारणीय निष्पादन
   |  Pinecone | Neo4j | MongoDB     |     कोई LLM नहीं। शुद्ध सॉफ्टवेयर तर्क।
   +----------------------------------+
```

1. **Classifier** इनपुट को प्रासंगिक डोमेन में रूट करता है।
2. **डोमेन एजेंट** (Profiler, Temporal, Summarizer, Code, Snippet, Image) समानांतर में संरचित डेटा निकालते हैं।
3. **Judge Agent** प्रत्येक निष्कर्षण की तुलना मौजूदा मेमोरी से करता है और निर्णय लेता है: ADD, UPDATE, DELETE, या NOOP।
4. **Weaver** Judge के निर्णयों को सभी भंडारण बैकएंड में निर्धारक रूप से निष्पादित करता है। कोर को एक स्टैंडअलोन Rust क्रेट के रूप में लागू किया जाता है कोई LLM निर्भरता के साथ।

**उच्च-प्रयास मोड** स्वचालित रूप से लंबे इनपुट को ओवरलैपिंग चंक (~200 टोकन) में विभाजित करता है और उन्हें समानांतर में संसाधित करता है, फिर लंबी बातचीत में कुछ भी मिस न हो इसके लिए परिणामों को मर्ज करता है।

### रिट्रीवल फ्लो

```
यूजर क्वेरी
    |
    v
+----------------------------------+
|       Retrieval LLM              |
|  यह निर्धारित करता है कि कौन से  |
|  टूल को कॉल करना है:             |
|  SearchProfile, SearchTemporal,  |
|  SearchSummary, SearchSnippet    |
+----------------+-----------------+
                 |
    +------------+------------+
    v            v            v
 Pinecone      Neo4j      Pinecone        समानांतर सर्च निष्पादन
 (profiles)   (events)   (summaries)
    |            |            |
    +------------+------------+
                 v
+----------------------------------+
|   उत्तर संश्लेषण + साइटेशन        |    LLM स्रोतों के साथ उत्तर उत्पन्न करता है
+----------------------------------+
```

### भंडारण

<table>
  <tr>
    <th>इंजन</th>
    <th>उद्देश्य</th>
    <th>के लिए प्रयुक्त</th>
  </tr>
  <tr>
    <td><strong>Pinecone</strong></td>
    <td>उच्च गति वेक्टर समानता सर्च</td>
    <td>प्रोफाइल, सारांश, स्निपेट, कोड एनोटेशन</td>
  </tr>
  <tr>
    <td><strong>Neo4j</strong></td><td>ग्राफ ट्रैवर्सल + समय-आधारित तर्क</td><td>घटनाएं, कोड ज्ञान ग्राफ, एनोटेशन</td>
    <td>ग्राफ ट्रैवर्सल + अस्थायी तर्क</td>
    <td>घटनाएं, कोड ज्ञान ग्राफ, एनोटेशन</td>
  </tr>
  <tr>
    <td><strong>MongoDB</strong></td>
    <td>कच्चा दस्तावेज़ भंडारण</td>
    <td>स्कैन किया गया कोड, फ़ाइल मेटाडेटा, स्कैन स्थिति</td>
  </tr>
</table>

> [!NOTE]
> स्थानीय परिनियोजन के लिए, Pinecone को **Chroma**, **pgvector**, या **SQLite** वेक्टर स्टोर के साथ प्रतिस्थापित किया जा सकता है।

## बेंचमार्क

हमने XMem को दो प्रतिष्ठित शैक्षणिक बेंचमार्क पर हर प्रमुख मेमोरी समाधान के खिलाफ परीक्षा की। XMem पूरे बोर्ड में बेहतर प्रदर्शन करता है।

### LoCoMo

मेमोरी पर रचनात्मक तर्क का परीक्षण करता है। क्या सिस्टम विभिन्न बातचीत में तथ्यों को जोड़ सकता है, अस्थायी संबंधों के बारे में तर्क कर सकता है, और खुले सिरे के प्रश्नों का उत्तर दे सकता है?

<table>
  <tr>
    <th>विधि</th>
    <th>एकल-हॉप (%)</th>
    <th>मल्टी-हॉप (%)</th>
    <th>खुली डोमेन (%)</th>
    <th>अस्थायी (%)</th>
    <th>समग्र (%)</th>
  </tr>
  <tr><td><strong>XMEM (हमारा)</strong></td><td><strong>90.6</strong></td><td><strong>92.3</strong></td><td><strong>91.2</strong></td><td><strong>91.9</strong></td><td><strong>91.5</strong></td></tr>
  <tr><td>Zep</td><td>74.11</td><td>66.04</td><td>67.71</td><td>79.79</td><td>75.14</td></tr>
  <tr><td>Memobase (v0.0.37)</td><td>70.92</td><td>46.88</td><td>77.17</td><td>85.05</td><td>75.78</td></tr>
  <tr><td>Mem0g (YC 24)</td><td>65.71</td><td>47.19</td><td>75.71</td><td>58.13</td><td>68.44</td></tr>
  <tr><td>Mem0 (YC 24)</td><td>67.13</td><td>51.15</td><td>72.93</td><td>55.51</td><td>66.88</td></tr>
  <tr><td>LangMem</td><td>62.23</td><td>47.92</td><td>71.12</td><td>23.43</td><td>58.10</td></tr>
  <tr><td>OpenAI</td><td>63.79</td><td>42.92</td><td>62.29</td><td>21.71</td><td>52.90</td></tr>
</table>

> बहु-हॉप तर्क पर (विभिन्न बातचीत से तथ्यों को जोड़ना), XMem अगले सर्वश्रेष्ठ सिस्टम को **26.3 अंक** से हराता है। कुल मिलाकर, XMem **91.5%** पर सभी सिस्टमों का नेतृत्व करता है, जो Zep से 75.14 पर आगे है।

### LongMemEval-S

दीर्घकालीन संवादी मेमोरी के लिए उद्योग मानक बेंचमार्क। यह परीक्षण करता है कि क्या कोई सिस्टम तथ्य याद रख सकता है, प्राथमिकता परिवर्तन को ट्रैक कर सकता है, समय के बारे में तर्क कर सकता है, और सत्रों के बीच संदर्भ बनाए रख सकता है।

<table>
  <tr>
    <th>श्रेणी</th>
    <th>XMem (Gemini 3-flash)</th>
    <th>Backboard.io (GPT-4o)</th>
    <th>Mastra (GPT-4o)</th>
    <th>Supermemory (GPT-4o)</th>
  </tr>
  <tr><td><strong>मल्टी-सेशन</strong></td><td><strong>93.6</strong></td><td>91.7</td><td>79.7</td><td>71.43</td></tr>
  <tr><td><strong>अस्थायी तर्क</strong></td><td><strong>94.5</strong></td><td>91.7</td><td>85.7</td><td>76.69</td></tr>
  <tr><td><strong>एकल-सेशन सहायक</strong></td><td><strong>96.43</strong></td><td>98.2</td><td>82.1</td><td>96.43</td></tr>
  <tr><td><strong>एकल-सेशन उपयोगकर्ता</strong></td><td><strong>97.1</strong></td><td>97.1</td><td>98.6</td><td>97.14</td></tr>
  <tr><td><strong>ज्ञान अपडेट</strong></td><td><strong>91.2</strong></td><td>93.6</td><td>85.9</td><td>88.46</td></tr>
  <tr><td><strong>एकल-सेशन प्राथमिकता</strong></td><td><strong>87.0</strong></td><td>90.0</td><td>73.3</td><td>70.0</td></tr>
</table>

> XMem Backboard.io के साथ सभी श्रेणियों में मेल खाता है, दोनों सत्र रिकॉल और प्राथमिकता ट्रैकिंग पर near-perfect स्कोर करते हैं। XMem Mastra को **9.2 अंक** से और Supermemory को **11.8 अंक** से बेहतर प्रदर्शन करता है।

### हम कैसे बेंचमार्क करते हैं
- **मूल्यांकन**: LLM-as-Judge Gemini का उपयोग करके संरचित रूब्रिक के साथ
- **निष्पक्षता**: सभी सिस्टम समान बातचीत इतिहास और क्वेरी के साथ परीक्षा की जाती है

## त्वरित शुरुआत

### स्थानीय XMem

```bash
npx create-xmem@latest
cd xmem
npm run dev
```

यह Windows, macOS, और Linux पर काम करता है। यह एक स्थानीय XMem वर्कस्पेस बनाता है, बैकएंड स्थापित करता है, स्थानीय भंडारण शुरू करता है, Chrome एक्सटेंशन बनाता है, और API को `http://localhost:8000` पर लॉन्च करता है।

स्थानीय पूर्वापेक्षाएं:

- Git
- Node.js 20+
- Python 3.11+
- Docker Desktop
- Ollama, जब तक कि आप `.env` में क्लाउड LLM कुंजी न जोड़ें

सेटअप के बाद, निम्न से एक्सटेंशन लोड करें:

```text
repos/xmem-extension/dist
```

Chrome पथ: `chrome://extensions` -> डेवलपर मोड सक्षम करें -> अनपैक किए गए को लोड करें।

### स्थानीय कमांड

```bash
npm run setup
npm run start
npm run verify
npm run doctor
```

यदि `.env` एक वास्तविक क्लाउड LLM कुंजी रखता है, XMem उस प्रदाता का उपयोग करता है और FastEmbed के साथ एम्बेडिंग को स्थानीय रखता है। यदि कोई क्लाउड कुंजी कॉन्फ़िगर नहीं है, XMem स्थानीय Ollama में फॉलबैक करता है और सेटअप के दौरान आवश्यक स्थानीय मॉडल खींचता है।

### संदर्भ पोर्टेबिलिटी

```bash
npm run context:export
npm run context:import -- --file ./exports/xmem-context.json
npm run context:sync -- --file ./exports/xmem-context.json --server https://api.xmem.in --api-key <key>
```

`context:export` एक स्थानीय संदर्भ बंडल लिखता है जिसे बाद में आयात किया जा सकता है या एक XMem सर्वर में सिंक किया जा सकता है।

### रिपोजिटरी को अनुक्रमित करें

```bash
python -m src.scanner.runner \
  --org your-org \
  --repo your-repo \
  --url https://github.com/your-org/your-repo.git \
  --enrich
```

> [!TIP]
> पूरी तरह से स्थानीय सेटअप के लिए कोई क्लाउड निर्भरता के साथ:
> ```ini
> FALLBACK_ORDER='["ollama"]'
> EMBEDDING_PROVIDER=ollama
> VECTOR_STORE_PROVIDER=pgvector
> ```
> फिर स्थानीय अतिरिक्त स्थापित करें: `pip install -e ".[local]"`

## कॉन्फ़िगरेशन

XMem अत्यधिक कॉन्फ़िगरेबल है। किसी भी एजेंट के मॉडल को ओवरराइड करें, फॉलबैक चेन को ट्यून करें, या गुणवत्ता/गति ट्रेडऑफ को समायोजित करें।

<table>
  <tr>
    <th>सेटिंग</th>
    <th>डिफ़ॉल्ट</th>
    <th>विवरण</th>
  </tr>
  <tr><td><code>FALLBACK_ORDER</code></td><td><code>openrouter,gemini,claude,openai</code></td><td>प्रदाता फॉलबैक अनुक्रम</td></tr>
  <tr><td><code>DEEPSEEK_API_KEY</code></td><td>खाली</td><td>आधिकारिक OpenAI-संगत एंडपॉइंट के लिए DeepSeek API कुंजी</td></tr>
  <tr><td><code>MIMO_API_KEY</code></td><td>खाली</td><td>आधिकारिक OpenAI-संगत एंडपॉइंट के लिए Xiaomi MiMo API कुंजी</td></tr>
  <tr><td><code>CLASSIFIER_MODEL</code></td><td>डिफ़ॉल्ट मॉडल</td><td>classifier एजेंट के लिए मॉडल को ओवरराइड करें</td></tr>
  <tr><td><code>JUDGE_MODEL</code></td><td>डिफ़ॉल्ट मॉडल</td><td>judge एजेंट के लिए मॉडल को ओवरराइड करें</td></tr>
  <tr><td><code>RETRIEVAL_MODEL</code></td><td>डिफ़ॉल्ट मॉडल</td><td>रिट्रीवल संश्लेषण के लिए मॉडल को ओवरराइड करें</td></tr>
  <tr><td><code>EMBEDDING_MODEL</code></td><td><code>gemini-embedding-001</code></td><td>पाठ एम्बेडिंग मॉडल</td></tr>
  <tr><td><code>EMBEDDING_PROVIDER</code></td><td><code>auto</code></td><td>auto, gemini, bedrock, ollama, fastembed</td></tr>
  <tr><td><code>VECTOR_STORE_PROVIDER</code></td><td><code>pinecone</code></td><td>pinecone, pgvector, chroma, sqlite</td></tr>
  <tr><td><code>PINECONE_DIMENSION</code></td><td><code>768</code></td><td>एम्बेडिंग वेक्टर आयाम</td></tr>
  <tr><td><code>RATE_LIMIT</code></td><td><code>60</code></td><td>प्रति मिनट API अनुरोध</td></tr>
  <tr><td><code>TEMPERATURE</code></td><td><code>0.4</code></td><td>LLM जनरेशन तापमान</td></tr>
</table>

---

<div align="center">
  <p><strong>XMem के साथ निर्माण को जारी रखें।</strong></p>
  <p>
    <a href="https://github.com/XortexAI/XMem">GitHub</a> &nbsp;•&nbsp;
    <a href="https://docs.xmem.in">Docs</a> &nbsp;•&nbsp;
    <a href="https://community.xmem.in">Community</a>
  </p>
</div>
