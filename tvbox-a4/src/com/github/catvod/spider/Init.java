package com.github.catvod.spider;

import android.content.Context;

/**
 * TVBox 加载 jar 后可能会反射调用 Init.init(Context)。
 * 这里只做最简初始化，确保 Android 4.0 上不触发任何新 API。
 */
public class Init {

    private static Context context;

    public static void init(Context ctx) {
        context = ctx;
    }

    public static Context get() {
        return context;
    }
}
