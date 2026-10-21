package com.github.catvod.spider;

import android.content.Context;

import com.github.catvod.crawler.Spider;

import java.util.HashMap;
import java.util.List;

/**
 * 面向 Android 4.0 (API 14) 的最小可用 spider。
 *
 * 只使用 Android 4.0 已有的 API：
 * - 不使用 Java 8 的 lambda / 默认方法 / Stream
 * - 不使用 java.util.Base64、StandardCharsets、java.time、OkHttp 等新库
 * - 单 dex，方法数远低于 65536
 *
 * 首页能看到“Android4演示”分类和“JAR 加载成功”条目，即表示加载成功。
 */
public class Android4Demo extends Spider {

    private static final String DEMO_ID = "demo_1";

    private static final String HOME =
            "{\"class\":[{\"type_id\":\"demo\",\"type_name\":\"Android4演示\"}],\"filters\":{}}";

    private static final String VIDEO =
            "{\"list\":[{\"vod_id\":\"" + DEMO_ID + "\",\"vod_name\":\"JAR 加载成功\","
                    + "\"vod_pic\":\"\",\"vod_remarks\":\"Android 4.0\"}]}";

    private static final String CATEGORY =
            "{\"page\":1,\"pagecount\":1,\"limit\":20,\"total\":1,\"list\":["
                    + "{\"vod_id\":\"" + DEMO_ID + "\",\"vod_name\":\"JAR 加载成功\","
                    + "\"vod_pic\":\"\",\"vod_remarks\":\"Android 4.0\"}]}";

    private static final String DETAIL =
            "{\"list\":[{\"vod_id\":\"" + DEMO_ID + "\",\"vod_name\":\"JAR 加载成功\","
                    + "\"vod_pic\":\"\",\"type_name\":\"演示\",\"vod_year\":\"2026\","
                    + "\"vod_area\":\"\",\"vod_remarks\":\"Android 4.0 兼容\","
                    + "\"vod_actor\":\"\",\"vod_director\":\"\","
                    + "\"vod_content\":\"能看到此页面，说明 jar 已经被 TVBox 成功加载。\","
                    + "\"vod_play_from\":\"演示\",\"vod_play_url\":\"第1集$\"}]}";

    private static final String EMPTY_LIST = "{\"list\":[]}";

    private static final String PLAYER =
            "{\"parse\":0,\"playUrl\":\"\",\"url\":\"\",\"header\":\"\"}";

    private String extend = "";

    @Override
    public void init(Context context, String extend) {
        this.extend = extend == null ? "" : extend;
    }

    /** 兼容旧版 TVBox 的初始化方法。 */
    public void init(Context context) {
        init(context, "");
    }

    @Override
    public String homeContent(boolean filter) {
        return HOME;
    }

    @Override
    public String homeVideoContent() {
        return VIDEO;
    }

    @Override
    public String categoryContent(String tid, String pg, boolean filter, HashMap<String, String> extend) {
        return CATEGORY;
    }

    /** 兼容旧版 TVBox：第二个参数是 boolean 类型的翻页标记。 */
    public String categoryContent(String tid, boolean pg, boolean filter, HashMap<String, String> extend) {
        return CATEGORY;
    }

    @Override
    public String detailContent(List<String> ids) {
        return DETAIL;
    }

    @Override
    public String searchContent(String key, boolean quick) {
        return EMPTY_LIST;
    }

    @Override
    public String playerContent(String flag, String id, List<String> vipFlags) {
        return PLAYER;
    }

    @Override
    public boolean manualVideoCheck() {
        return false;
    }

    @Override
    public boolean isVideoFormat(String url) {
        return false;
    }
}
