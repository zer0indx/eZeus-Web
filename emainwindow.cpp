#include "emainwindow.h"

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#include <emscripten/html5.h>
#endif

#include "widgets/emainmenu.h"
#include "widgets/esettingsmenu.h"
#include "widgets/egamewidget.h"
#include "widgets/egameloadingwidget.h"
#include "widgets/egamemenu.h"
#include "widgets/emenuloadingwidget.h"
#include "widgets/eworldwidget.h"
#include "widgets/echoosegameeditmenu.h"
#include "widgets/eselectcolonywidget.h"

#include "audio/emusic.h"

#include "engine/ethreadpool.h"

#include "egamedir.h"

#include "fileIO/ereadstream.h"

#include <chrono>
#include <filesystem>
#include <fstream>

#include "widgets/efilewidget.h"
#include "elanguage.h"

#include "evectorhelpers.h"

#include "widgets/eeventbackground.h"
#include "widgets/eepisodeintroductionwidget.h"
#include "widgets/eepisodelostwidget.h"
#include "widgets/erosterofleaders.h"

eMainWindow::eMainWindow() {}

eMainWindow::~eMainWindow() {
    if(mSdlWindow) SDL_DestroyWindow(mSdlWindow);
    if(mSdlRenderer) SDL_DestroyRenderer(mSdlRenderer);
    setWidget(nullptr);
}

bool eMainWindow::initialize(const eSettings& settings) {
    const auto& res = settings.fRes;
    const int w = res.width();
    const int h = res.height();
    const auto window = SDL_CreateWindow("eZeus",
                                         SDL_WINDOWPOS_UNDEFINED,
                                         SDL_WINDOWPOS_UNDEFINED,
                                         w, h, SDL_WINDOW_SHOWN);

    if(!window) {
        printf("Window could not be created! SDL Error: %s\n",
               SDL_GetError());
        return false;
    }
    const Uint32 flags = SDL_RENDERER_ACCELERATED/* |
                         SDL_RENDERER_PRESENTVSYNC*/;
    const auto renderer = SDL_CreateRenderer(window, -1, flags);
    if(!renderer) {
        printf("Renderer could not be created! SDL Error: %s\n",
               SDL_GetError());
        SDL_DestroyWindow(window);
        return false;
    }

    if(mSdlWindow) SDL_DestroyWindow(mSdlWindow);
    if(mSdlRenderer) SDL_DestroyRenderer(mSdlRenderer);
    mSdlWindow = window;
    mSdlRenderer = renderer;
    setResolution(res);
    setFullscreen(settings.fFullscreen);
    mSettings = settings;
    SDL_SetWindowPosition(window, SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED);

    const std::string icoPath = eGameDir::path("zeus.ico");
    const auto icon = IMG_Load(icoPath.c_str());
    SDL_SetWindowIcon(window, icon);
    eGameTextures::setSettings(mSettings);
    return true;
}

void eMainWindow::setWidget(eWidget* const w) {
    if(mWidget) {
        if(mWidget != mGW && mWidget != mWW) {
            mWidget->deleteLater();
        }
    }
    mWidget = w;
}

eWidget* eMainWindow::takeWidget() {
    const auto w = mWidget;
    mWidget = nullptr;
    return w;
}

void eMainWindow::addSlot(const eSlot& slot) {
    mSlots.push_back(slot);
}

void eMainWindow::setResolution(const eResolution& res) {
    if(mSettings.fRes == res && !mFirstFullscrenSetting) return;
    mFirstResolutionSetting = false;
    mSettings.fRes = res;
    const int w = res.width();
    const int h = res.height();
    SDL_SetWindowSize(mSdlWindow, w, h);
#ifdef __EMSCRIPTEN__
    // The canvas is resized without a size-changed event reaching the
    // renderer, so it would keep drawing into the old area.
    SDL_RenderSetViewport(mSdlRenderer, nullptr);
#endif
}

void eMainWindow::setFullscreen(const bool f) {
    if(mSettings.fFullscreen == f && !mFirstFullscrenSetting) return;
    mFirstFullscrenSetting = false;
    mSettings.fFullscreen = f;
#ifdef __EMSCRIPTEN__
    // Browser fullscreen of the page's game container; the resolution then
    // follows the new window size in fitViewport(). Browsers only allow it
    // from user input, so the request waits for the next click or key.
    if(f) emscripten_request_fullscreen("#game", true);
    else emscripten_exit_fullscreen();
#else
    SDL_SetWindowFullscreen(mSdlWindow, f ? SDL_WINDOW_FULLSCREEN : 0);
#endif
}

#ifdef __EMSCRIPTEN__
eResolution eMainWindow::sViewportResolution() {
    // The interface needs at least 800x600 and is not laid out for windows
    // narrower than 4:3; the page scales and letterboxes the canvas instead.
    const int w = std::max(800, EM_ASM_INT({ return window.innerWidth; }));
    int h = std::max(600, EM_ASM_INT({ return window.innerHeight; }));
    h = std::min(h, 3*w/4);
    return eResolution(w, h);
}

// Widgets are laid out once when created, so only the main menu, which is
// cheap to rebuild, follows the browser window. Other screens keep their
// resolution and the page scales the canvas until the player gets back to
// the main menu.
void eMainWindow::fitViewport() {
    if(!dynamic_cast<eMainMenu*>(mWidget)) return;
    const auto res = sViewportResolution();
    if(res == mSettings.fRes) {
        mViewportChangedAt = 0;
        return;
    }
    // Wait for the window to settle, e.g. while it is being dragged.
    const double now = emscripten_get_now();
    if(mViewportChangedAt == 0) mViewportChangedAt = now;
    if(now - mViewportChangedAt < 300) return;
    mViewportChangedAt = 0;
    setResolution(res);
    eGameTextures::setSettings(mSettings);
    // Loads interface textures for the new UI scale if needed.
    showMenuLoading();
}
#endif

void eMainWindow::runBusy(const eAction& a) {
#ifdef __EMSCRIPTEN__
    sSetBusy(true, true);
    // Run it a couple of frames later so the browser shows the indicator.
    mBusyAction = a;
    mBusyFrames = 2;
#else
    a();
#endif
}

void eMainWindow::sSetBusy(const bool busy, const bool indicator) {
#ifdef __EMSCRIPTEN__
    // SDL feeds audio from the main thread; while it is blocked the browser
    // keeps repeating the last buffer, so suspend audio instead.
    EM_ASM({ if(Module.setBusy) Module.setBusy(!!$0, !!$1); },
           busy, indicator);
#else
    (void)busy;
    (void)indicator;
#endif
}

void eMainWindow::startGameAction(eGameBoard* const board,
                                  const eGameWidgetSettings& settings) {
    const auto show = [this, board, settings]() {
        showGame(board, settings);
    };
    startGameAction(show);
}

void eMainWindow::startGameAction(const stdsptr<eCampaign>& c,
                                  const eGameWidgetSettings& settings) {
    const auto show = [this, c, settings]() {
        showGame(c, settings);
    };
    startGameAction(show);
}

void eMainWindow::startGameAction(const eAction& a) {
    clearWidgets();
    const auto l = new eGameLoadingWidget(this);
    l->resize(width(), height());
    l->setDoneAction(a);
    setWidget(l);
    l->initialize();
}

void eMainWindow::showEpisodeIntroduction(
        const stdsptr<eCampaign>& c) {
    clearWidgets();
    if(c) mCampaign = c;
    const auto e = new eEpisodeIntroductionWidget(this);
    const auto proceedA = [this]() {
        runBusy([this]() {
            mCampaign->startEpisode();
            const auto dir = leaderSaveDir();
            saveGame(dir + "autosave replay.ez");
            startGameAction([this]() {
                eGameWidgetSettings settings;
                settings.fPaused = true;
                showGame(mCampaign, settings);
            });
        });
    };
    e->resize(width(), height());
    const auto ee = mCampaign->currentEpisode();

    const auto path = mCampaign->currentEpisodeAudioFilePath(true);
    const bool played = eMusic::playCampaignVoice(path);
    if(!played) eMusic::playMissionIntroMusic();

    e->initialize(mCampaign,
                  mCampaign->titleText(),
                  ee->fIntroduction,
                  ee->fGoals,
                  proceedA,
                  eEpisodeIntroType::intro);
    setWidget(e);
}

std::string eMainWindow::leaderSaveDir() const {
    return eGameDir::saveDir() + mLeader + "/";
}

void eMainWindow::clearWidgets() {
    if(mGW && mWidget != mGW) {
        mGW->setBoard(nullptr);
        mGW->deleteLater();
        mGW = nullptr;
    }
    if(mWW && mWidget != mWW) {
        mWW->deleteLater();
        mWW = nullptr;
    }
}

void eMainWindow::episodeFinished() {
    clearWidgets();
    if(!mCampaign) return;
    mCampaign->episodeFinished();
    const bool f = mCampaign->finished();
    if(f) return adventureComplete();
    const auto n = mCampaign->currentEpisodeType();
    if(n == eEpisodeType::parentCity) {
        showEpisodeIntroduction();
    } else {
        const auto w = new eSelectColonyWidget(this);
        const auto sel = mCampaign->remainingColonies();
        const auto selA = [this](const stdsptr<eWorldCity>& c) {
            int cid = 0;
            const auto& eps = mCampaign->colonyEpisodes();
            for(const auto& e : eps) {
                if(e->fCity == c) break;
                cid++;
            }
            mCampaign->setCurrentColonyEpisode(cid);
            showEpisodeIntroduction();
        };
        w->resize(width(), height());
        w->initialize(sel, selA, &mCampaign->worldBoard());
        setWidget(w);
    }
}

void eMainWindow::adventureComplete() {
    clearWidgets();
    if(!mCampaign) return;
    const auto e = new eEpisodeIntroductionWidget(this);
    const auto proceedA = [this]() {
        showMainMenu();
    };
    e->resize(width(), height());

    const auto path = mCampaign->adventureVictoryAudioFilePath();
    const bool played = eMusic::playCampaignVoice(path);
    if(!played) eMusic::playCampaignVictoryMusic();

    e->initialize(mCampaign,
                  eLanguage::zeusText(62, 0),
                  mCampaign->completeText(),
                  {},
                  proceedA,
                  eEpisodeIntroType::campaingVictory);
    setWidget(e);
}

void eMainWindow::episodeLost() {
    clearWidgets();
    const auto e = new eEpisodeLostWidget(this);
    const auto proceedA = [this]() {
        showMainMenu();
    };
    e->resize(width(), height());
    e->initialize(proceedA);
    setWidget(e);
}

bool eMainWindow::saveGame(const std::string& path) {
    const auto fsp = std::filesystem::path(path);
    const auto fspd = fsp.parent_path();
    std::filesystem::create_directories(fspd);
    std::ofstream file(path, std::ios::out | std::ios::binary |
                       std::ios::trunc);
    if(!file) return false;
    eWriteTarget target(&file);
    eWriteStream dst(target);
    dst.writeFormat("eZeus.ez");
    if(mGW) {
        const auto s = mGW->settings();
        s.write(dst);
    } else {
        eGameWidgetSettings s;
        s.fPaused = true;
        s.write(dst);
    }
    mCampaign->write(dst);
    file.close();
    return true;
}

bool eMainWindow::loadGame(const std::string& path) {
    // Read the whole file at once; the many small reads below are slow on
    // browser storage.
    std::ifstream file(path, std::ios::in | std::ios::binary | std::ios::ate);
    if(!file) return false;
    std::vector<char> data(static_cast<size_t>(file.tellg()));
    file.seekg(0);
    file.read(data.data(), data.size());
    file.close();
    eReadSource source(data.data());
    eReadStream src(source);
    src.readFormat();
    const auto& format = src.format();
    const int version = src.formatVersion();
    if(format != "eZeus.ez") {
        printf("Invalid file '%s' format '%s', expected 'eZeus.ez'.\n",
               path.c_str(), format.c_str());
        return false;
    }
    if(version > eFileFormat::version) {
        printf("Attempting to read '%s' format '%s' version '%i' newer than the executable.\n",
               path.c_str(), format.c_str(), version);
    }
    eGameWidgetSettings s;
    s.read(src);
    const auto c = std::make_shared<eCampaign>();
    c->read(src);
    c->loadStrings();
    c->loadNumbers();
    src.handlePostFuncs();

    startGameAction(c, s);
    return true;
}

void eMainWindow::closeGame() {
    if(!mGW) return;
    if(mGW) {
        mGW->setBoard(nullptr);
        mGW->deleteLater();
        mGW = nullptr;
    }
    if(mWW) {
        mWW->deleteLater();
        mWW = nullptr;
    }
    showMainMenu();
}

void eMainWindow::showRosterOfLeaders() {
    clearWidgets();
    eMusic::playMenuMusic();
    const auto rol = new eRosterOfLeaders(this);
    rol->resize(width(), height());
    rol->initialize();
    setWidget(rol);
}

void eMainWindow::showMenuLoading() {
    const auto mlw = new eMenuLoadingWidget(this);
    mlw->setDoneAction([this]() {
        const auto ls = eRosterOfLeaders::sLeaders();
        if(ls.size() == 1) setLeader(ls[0]);
        if(mLeader.empty()) {
            showRosterOfLeaders();
        } else {
            showMainMenu();
        }
    });
    mlw->initialize();
    mlw->resize(width(), height());
    setWidget(mlw);
}

void eMainWindow::showMainMenu() {
    mCampaign = nullptr;
    clearWidgets();
    eMusic::playMenuMusic();

    const auto mm = new eMainMenu(this);
    mm->resize(width(), height());
    setWidget(mm);

    const auto newGameAction = [this]() {
        showChooseGameMenu();
    };

    const auto loadGameAction = [this, mm]() {
        const auto fw = new eFileWidget(this);
        const auto func = [this](const std::string& path) {
            return loadGame(path);
        };
        const auto closeAct = [mm, fw]() {
            mm->removeWidget(fw);
            fw->deleteLater();
        };
        const auto dir = leaderSaveDir();
        fw->intialize(eLanguage::zeusText(1, 3),
                      dir, func, closeAct);
        mm->addWidget(fw);
        fw->align(eAlignment::center);
    };

    const auto editGameAction = [this]() {
        showChooseGameEditMenu();
    };

    const auto settingsAction = [this]() {
        showSettingsMenu();
    };

    const auto quitAction = [this]() {
        mQuit = true;
    };

    const auto leaderAction = [this]() {
        showRosterOfLeaders();
    };

    mm->initialize(newGameAction,
                   loadGameAction,
                   editGameAction,
                   settingsAction,
                   quitAction,
                   leaderAction);
}

void eMainWindow::showSettingsMenu() {
    const auto esm = new eSettingsMenu(mSettings, this);
    esm->resize(width(), height());

    const auto applyA = [this](const eSettings& settings) {
        const bool loadNeeded = settings.fRes != mSettings.fRes;
        setResolution(settings.fRes);
        setFullscreen(settings.fFullscreen);
        mSettings = settings;
        mSettings.write();
        if(!mSettings.fTinyTextures &&
           !mSettings.fSmallTextures &&
           !mSettings.fMediumTextures &&
           !mSettings.fLargeTextures) {
            mSettings.fSmallTextures = true;
        }
        eGameTextures::setSettings(mSettings);
        if(loadNeeded) showMenuLoading();
        else showMainMenu();
    };
    const auto fullscrennA = [this](const bool f) {
        setFullscreen(f);
    };
    esm->initialize(applyA, fullscrennA);
    setWidget(esm);
}

void eMainWindow::showChooseGameMenu() {
    const auto gem = new eChooseGameEditMenu(this);
    gem->resize(width(), height());
    gem->initialize(false);
    setWidget(gem);
}

void eMainWindow::showChooseGameEditMenu() {
    const auto gem = new eChooseGameEditMenu(this);
    gem->resize(width(), height());
    gem->initialize(true);
    setWidget(gem);
}

void eMainWindow::showGame(const stdsptr<eCampaign>& c,
                           const eGameWidgetSettings& settings) {
    mCampaign = c;
    const auto e = c->currentEpisode();
    showGame(e->fBoard, settings);
}

void eMainWindow::showGame(eGameBoard* b,
                           const eGameWidgetSettings& settings) {
    if(!b) b = mBoard;

    if(b == mBoard && mGW) {
        return setWidget(mGW);
    }

    if(mGW) {
        mGW->setBoard(nullptr);
        mGW->deleteLater();
        mGW = nullptr;
    }

    mBoard = b;
    if(mBoard) {
        mBoard->updateAppealMapIfNeeded();
        mBoard->waitUntilFinished();
    }

    eMusic::playRandomMusic();
    mGW = new eGameWidget(this);
    mGW->setBoard(b);
    mGW->resize(width(), height());
    mGW->initialize();
    mGW->setSettings(settings);
    setWidget(mGW);
}

void eMainWindow::showWorld() {
    if(mWidget == mWW) return;
    if(!mCampaign) return;
    if(!mWW) {
        mWW = new eWorldWidget(this);
        mWW->resize(width(), height());
        mWW->initialize();
        mWW->setBoard(mBoard);
    } else {
        mWW->update();
    }
    setWidget(mWW);
}

void eMainWindow::execDialog(
        eWidget* const d, const bool closable,
        const eAction &closeFunc,
        eWidget* const parent) {
    if(!mWidget) return;
    const auto bg = new eEventBackground(this);
    if(closeFunc) {
        bg->initialize(parent ? parent : mWidget, d, closable, closeFunc);
    } else {
        const auto closeFunc = [d]() {
            d->deleteLater();
        };
        bg->initialize(parent ? parent : mWidget, d, closable, closeFunc);
    }
}

class eTooltip {
public:
    eTooltip(eMainWindow& w) : mWindow(w) {}

    void update() {
        const auto txt = eWidget::sTooltip();
        const bool updateTxt = mText != txt;
        if(updateTxt) {
            mText = txt;
        }

        const auto& res = mWindow.resolution();
        const int fontSize = res.verySmallFontSize();
        const bool updateFont = mFontSize != fontSize;
        if(updateFont) {
            mFontSize = fontSize;
            mFont = eFonts::defaultFont(mFontSize);
        }

        const bool updateTexture = updateTxt || updateFont;
        if(updateTexture) {
            const auto r = mWindow.renderer();
            if(mText.empty()) {
                mTexture->reset();
            } else {
                mTexture->loadText(r, mText, eFontColor::light, *mFont, 50*fontSize);
            }
        }
    }

    void paint(const int x, const int y, ePainter& p) {
        const int pp = padding();
        SDL_Rect rect{x, y, width(), height()};
        p.fillRect(rect, SDL_Color{16, 108, 144, 255});
        p.drawRect(rect, SDL_Color{0, 32, 32, 255}, 1);
        p.drawTexture(x + pp, y + pp, mTexture);
    }

    int width() const { return mTexture->width() + 2*padding(); }
    int height() const { return mTexture->height() + 2*padding(); }

    bool empty() const { return mText.empty(); }
private:
    int padding() const { return mFontSize/2; }

    eMainWindow& mWindow;
    int mFontSize = -1;
    TTF_Font* mFont = nullptr;
    std::string mText;
    stdsptr<eTexture> mTexture = std::make_shared<eTexture>();
};

int eMainWindow::exec() {
    using namespace std::chrono;
    using namespace std::chrono_literals;

    showMenuLoading();

    eMouseButton button{eMouseButton::none};
    eMouseButton buttons{eMouseButton::none};

    SDL_Event e;
    eTooltip tooltip(*this);

    const bool showFPS = false;
    const double fpsClamp = 20;

    int c = 0;
    int fpsVal = 0;
    bool resetRenderTargets = false;
    // Captured by value so the state outlives exec() when the browser
    // drives the loop through emscripten_set_main_loop.
    auto frame = [=]() mutable {
        const auto fpsStart = high_resolution_clock::now();
#ifdef __EMSCRIPTEN__
        if(mBusyAction && --mBusyFrames <= 0) {
            const auto a = std::move(mBusyAction);
            mBusyAction = nullptr;
            a();
            sSetBusy(false, true);
        }
        fitViewport();
#endif

        while(SDL_PollEvent(&e)) {
            int x, y;
            SDL_GetMouseState(&x, &y);
            const bool shift = mShiftPressed > 0;
            const bool ctrl = mCtrlPressed > 0;
            if(e.type == SDL_QUIT) {
                mQuit = true;
            } else if(e.type == SDL_WINDOWEVENT) {
                const auto we = e.window.event;
                if(we == SDL_WINDOWEVENT_MINIMIZED) {
                    resetRenderTargets = true;
#ifndef __EMSCRIPTEN__
                    while(SDL_WaitEvent(&e)) {
                        if(e.window.event == SDL_WINDOWEVENT_RESTORED) {
                            break;
                        }
                    }
#endif
                } else if(we == SDL_WINDOWEVENT_EXPOSED) {
                    resetRenderTargets = true;
                }
            } else if(e.type == SDL_RENDER_TARGETS_RESET ||
                      e.type == SDL_RENDER_DEVICE_RESET) {
                resetRenderTargets = true;
            } else if(e.type == SDL_MOUSEMOTION) {
                const eMouseEvent me(x, y, shift, ctrl, buttons, button);
                if(mWidget) mWidget->mouseMove(me);
            } else if(e.type == SDL_MOUSEBUTTONDOWN) {
                switch(e.button.button) {
                case SDL_BUTTON_LEFT:
                    button = eMouseButton::left;
                    break;
                case SDL_BUTTON_RIGHT:
                    button = eMouseButton::right;
                    break;
                case SDL_BUTTON_MIDDLE:
                    button = eMouseButton::middle;
                    break;
                default: continue;
                }
                buttons = button | buttons;

                const eMouseEvent me(x, y, shift, ctrl, buttons, button);
                if(mWidget) mWidget->mousePress(me);
            } else if(e.type == SDL_MOUSEBUTTONUP) {
                switch(e.button.button) {
                case SDL_BUTTON_LEFT:
                    button = eMouseButton::left;
                    break;
                case SDL_BUTTON_RIGHT:
                    button = eMouseButton::right;
                    break;
                case SDL_BUTTON_MIDDLE:
                    button = eMouseButton::middle;
                    break;
                default: continue;
                }
                buttons = buttons & ~button;
                const eMouseEvent me(x, y, shift, ctrl, buttons, button);
                if(mWidget) mWidget->mouseRelease(me);
            } else if(e.type == SDL_MOUSEWHEEL) {
                const eMouseWheelEvent me(x, y, shift, ctrl, buttons, e.wheel.y);
                if(mWidget) mWidget->mouseWheel(me);
            } else if(e.type == SDL_KEYDOWN) {
                const auto k = e.key.keysym.scancode;
                if(k == SDL_Scancode::SDL_SCANCODE_LSHIFT ||
                   k == SDL_Scancode::SDL_SCANCODE_RSHIFT) {
                    mShiftPressed++;
                } else if(k == SDL_Scancode::SDL_SCANCODE_LCTRL ||
                          k == SDL_Scancode::SDL_SCANCODE_RCTRL) {
                    mCtrlPressed++;
                }
                const eKeyPressEvent ke(x, y, shift, ctrl, buttons, k);
                if(mWidget) mWidget->keyPress(ke);
            } else if(e.type == SDL_KEYUP) {
                const auto k = e.key.keysym.scancode;
                if(k == SDL_Scancode::SDL_SCANCODE_LSHIFT ||
                   k == SDL_Scancode::SDL_SCANCODE_RSHIFT) {
                    mShiftPressed--;
                } else if(k == SDL_Scancode::SDL_SCANCODE_LCTRL ||
                          k == SDL_Scancode::SDL_SCANCODE_RCTRL) {
                    mCtrlPressed--;
                }
            }
        }

        if(resetRenderTargets) {
            resetRenderTargets = false;
            if(mWidget) mWidget->renderTargetsReset();
        }

        SDL_SetRenderDrawColor(mSdlRenderer, 0x0, 0x0, 0x0, 0xFF);
        SDL_RenderClear(mSdlRenderer);

        ePainter p(mSdlRenderer);

        eMusic::incTime();
        if(mWidget) {
            mWidget->paint(p);
            tooltip.update();
            if(!tooltip.empty()) {
                const auto& res = resolution();
                const int pp = 25*res.multiplier();
                const int wtt = tooltip.width();
                const int htt = tooltip.height();
                int mx, my;
                SDL_GetMouseState(&mx, &my);
                int xtt;
                int ytt;
                if(mx > width()/2) {
                    xtt = mx - wtt;
                } else {
                    xtt = mx;
                }
                if(my > height()/2) {
                    ytt = my - htt - pp;
                } else {
                    ytt = my + pp;
                }
                tooltip.paint(xtt, ytt, p);
            }
        }

        if(showFPS) {
            p.setFont(eFonts::defaultFont(resolution()));
            p.drawText(0, 0, std::to_string(fpsVal), eFontColor::dark);
        }

        SDL_RenderPresent(mSdlRenderer);

        for(const auto& s : mSlots) {
            s();
        }
        mSlots.clear();

        const auto fpsEnd = high_resolution_clock::now();
        const duration<double, std::milli> fpsElapsed = fpsEnd - fpsStart;
        const duration<double, std::milli> fpsDuration(1000./fpsClamp);
        const duration<double, std::milli> fpsSleep(fpsDuration - fpsElapsed);
#ifndef __EMSCRIPTEN__
        std::this_thread::sleep_for(fpsSleep);
#else
        (void)fpsSleep;
        if(mQuit) emscripten_cancel_main_loop();
#endif

        if(showFPS) {
            c++;
            if(c % 25 == 0) {
                const auto fpsEnd = high_resolution_clock::now();
                const duration<double, std::milli> fpsElapsed = fpsEnd - fpsStart;
                fpsVal = (int)std::round(1000./fpsElapsed.count());
            }
        }
    };

#ifdef __EMSCRIPTEN__
    const auto f = new std::function<void()>(std::move(frame));
    emscripten_set_main_loop_arg([](void* const arg) {
        (*static_cast<std::function<void()>*>(arg))();
    }, f, fpsClamp, true);
#else
    while(!mQuit) frame();
#endif

    return 0;
}
