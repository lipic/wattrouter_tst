function loadLibraryForPC(){var t=["https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css","https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css","https://cdn.jsdelivr.net/gh/gitbrent/bootstrap-switch-button@1.1.0/css/bootstrap-switch-button.min.css","https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css"];for(var s in t){var a=s;if(!document.getElementById(a)){var i=document.getElementsByTagName("head")[0],n=document.createElement("link");n.id=a,n.rel="stylesheet",n.type="text/css",n.href=t[s],n.media="all",i.appendChild(n)}}appendLibrary("main/static/cached-webpgr.js"),whenAvailable("requireScript",function(t){requireScript("jquery","3.5.1","https://code.jquery.com/jquery-3.5.1.min.js"),requireScript("moment","1.0.0","https://cdnjs.cloudflare.com/ajax/libs/moment.js/2.29.0/moment.min.js"),whenAvailable("$",function(){requireScript("i18n","1.0.0","https://cdnjs.cloudflare.com/ajax/libs/jquery.i18n/1.0.7/jquery.i18n.min.js"),requireScript("bootstrap","0.0.0","https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"),requireScript("bootstrap_switch_button","1.1.0","https://cdn.jsdelivr.net/gh/gitbrent/bootstrap-switch-button@1.1.0/dist/bootstrap-switch-button.min.js"),requireScript("gauge.min","0.0.0","http://bernii.github.io/gauge.js/dist/gauge.min.js"),requireScript("Chart","2.9.3","https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.9.3/Chart.min.js"),whenAvailable("Chart",function(){requireScript("chartjs_plugin","1.9.0","https://unpkg.com/chartjs-plugin-streaming@1.9.0/dist/chartjs-plugin-streaming.min.js"),requireScript("gaugeSetting","0.0.0","main/static/gauge.js"),requireScript("evse","0.0.0","main/static/evse.js"),requireScript("energyChart","0.0.0","main/static/energyChart.js"),requireScript("powerChart","0.0.0","main/static/powerChart.js"),appendLibrary("main/static/func.js"),appendLibrary("main/static/setting.js"),appendLibrary("main/static/dataTable.js"),appendLibrary("main/static/overView.js"),appendLibrary("main/static/translation.js")})})})}