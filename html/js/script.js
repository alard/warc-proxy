$(function(){

  function convertDataToNodes(data, collapse) {
    var nodes = [];
    if (data.children) {
      for (var i in data.children) {
        var children = convertDataToNodes(data.children[i], true);
        if (collapse && children.length == 1 && !data.children[i].uri) {
          var node = {
            title: i + children[0].title,
            uri: children[0].uri,
            isFolder: children[0].isFolder,
            children: children[0].children
          };
          nodes.push(node);
        } else {
          var node = {
            title: i,
            uri: data.children[i].uri,
            isFolder: (children.length > 0),
            children: children
          };
          nodes.push(node);
        }
      }
    }
    nodes.sort(function(a,b) {
      return (a.title < b.title) ? -1 : (a.title == b.title) ? 0 : 1;
    });
    return nodes;
  }

  $('#fileBrowserTree').dynatree({
    onActivate: function(node) {
      if (node.data.is_warc) {
        $('#fileBrowserPath').attr('value', node.data.path);
      }
    },
    initAjax: {
      url: '/browse.json', dataType: 'json', data: { path: '/' }
    },
    onLazyRead: function(node) {
      node.appendAjax({
        url: '/browse.json', dataType: 'json', data: { path: node.data.path }
      });
    }
  });

  function onClick_radioMimetypeButton(e) {
    var mimetypeBtn = $(e.target),
        li = mimetypeBtn.parents('li.file'),
        treeDiv = li.children('div.tree'),
        tree = treeDiv.dynatree("getTree");
    tree.options.initAjax.data.mime_type = mimetypeBtn.attr('data-mimetype');
    tree.reload();
  }

  function pathNameToId(path) {
    return path.replace(/[^-_a-zA-Z0-9]/g, '_');
  }

  function addFile(path) {
    $('#fileBrowserDialog').modal('hide');

    var basename = path.match(/[^\/\\]+$/)[0];
    var li_id = 'file-' + pathNameToId(path);
    if (document.getElementById(li_id)) {
      return;
    }

    var li = document.createElement('li');
    li.id = li_id;
    li.className = 'file file-loading';
    $(li).append(
      '<h2></h2>' +
      '<div class="btn-toolbar">' +
        '<div class="btn-group radio-mimetype" data-toggle="buttons-radio">' +
          '<button type="button" class="btn btn-small mimetype-text" data-mimetype="text/(plain|html)">Text</button>' +
          '<button type="button" class="btn btn-small" data-mimetype="image/">Images</button>' +
          '<button type="button" class="btn btn-small" data-mimetype=".">All</button>' +
        '</div>' +
        '<a href="#" class="btn btn-small pull-right btn-remove-file"><i class="icon-remove-sign"></i></a>' +
        '<div class="progress progress-striped active"><div class="bar" style="width: 0%"></div></div>' +
      '</div>' +
      '<div class="tree"></div>'
    );
    $(li).attr('data-path', path);
    $('h2', li).text(basename);
    $('.radio-mimetype button.mimetype-text', li).button('toggle');
    $('.radio-mimetype button', li).click(onClick_radioMimetypeButton);
    $('.btn-remove-file', li).click(onClick_unloadFile);
    $('#files-list').append(li);

    loadWarc(path, li.id);
  }

  function prepareFileUriTree(path, li_id) {
    $('#'+li_id+' .tree').dynatree({
      onActivate: function(node) {
        if (node.data.uri) {
          parent.archived_page.location.href = node.data.uri;
        }
      },
      classNames: {
        nodeIcon: 'icon-dynatree'
      },
      initAjax: {
        url: '/index.json', dataType: 'json',
        data: { path: path, mime_type: 'text/(plain|html)' },
        postProcess: function(d) { return convertDataToNodes(d); }
      }
    });
  }

  var loadWarcTimeouts = {};
  function loadWarc(path, li_id) {
    if (loadWarcTimeouts[path]) {
      window.clearTimeout(loadWarcTimeouts[path]);
    }

    $.ajax({
      url: '/load-warc',  type: 'POST', data: { path: path },
      dataType: 'json',
      success: function(data) {
        if (data.status == 'indexed') {
          $('#'+li_id).removeClass('file-loading');
          $('#'+li_id+' .progress').remove();
          prepareFileUriTree(path, li_id);

          updateAllWarcs();

        } else {
          if (data.bytes_read) {
            var perc = (100 * data.bytes_read / data.bytes_total);
            $('#'+li_id+' .progress .bar').css('width', perc+'%');
          }

          loadWarcTimeouts[path] = window.setTimeout(function() {
            loadWarc(path, li_id);
          }, 500);
        }
      }
    });
  }
  function unloadWarc(path) {
    if (loadWarcTimeouts[path]) {
      window.clearTimeout(loadWarcTimeouts[path]);
    }

    var li_id = 'file-'+pathNameToId(path);
    $.ajax({
      url: '/unload-warc',  type: 'POST', data: { path: path },
      dataType: 'json',
      success: function(data) {
        $('#'+li_id).remove();

        updateAllWarcs();
      }
    });
  }
  function updateAllWarcs() {
    $.ajax({
      url: '/list-warcs',  type: 'GET',
      dataType: 'json',
      success: function(data) {
        var t = data.paths.length;
        t += ' archive';
        if (data.paths.length != 1) {
          t += 's';
        }
        t += ', ' + data.uri_count + ' URL';
        if (data.uri_count != 1) {
          t += 's';
        }
        $('#global-stats').text(t);

        for (var i=0; i<data.paths.length; i++) {
          addFile(data.paths[i]);
        }
      }
    });
  }

  $('#form-add-file').submit(function(e) {
    e.stopPropagation();
    addFile(document.getElementById('fileBrowserPath').value);
    return false;
  });

  function onClick_unloadFile(e) {
    e.stopPropagation();
    var path = $(e.target).parents('li.file').attr('data-path');
    unloadWarc(path);
    return false;
  }

  updateAllWarcs();

});

