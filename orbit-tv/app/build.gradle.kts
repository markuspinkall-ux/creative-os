plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "de.orbitos.tv"
    compileSdk = 35

    defaultConfig {
        applicationId = "de.orbitos.tv"
        minSdk = 25
        targetSdk = 34
        versionCode = (System.getenv("ORBIT_TV_VERSION_CODE") ?: "1").toInt()
        versionName = System.getenv("ORBIT_TV_VERSION_NAME") ?: "1.0"
    }

    signingConfigs {
        create("orbit") {
            storeFile = file("orbit-tv.keystore")
            storePassword = "orbittv"
            keyAlias = "orbittv"
            keyPassword = "orbittv"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("orbit")
        }
        debug {
            signingConfig = signingConfigs.getByName("orbit")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    val media3 = "1.4.1"
    implementation("androidx.media3:media3-exoplayer:$media3")
    implementation("androidx.media3:media3-exoplayer-hls:$media3")
    implementation("androidx.media3:media3-ui:$media3")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.core:core-ktx:1.13.1")
}
