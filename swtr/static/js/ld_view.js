(function(window) {
  window.swtr = window.swtr || {};

  var LDSwts = Backbone.Collection.extend({
    getAll: function(options) {
      //get all sweets of ocd-anno type
      // error checking
      if(!options.what) {
        throw Error('"what" option must be passed to get sweets of a URI');
        return false;
      }
      // setting up params
      var what = options.what;
      url = swtr.swtstoreURL() + swtr.endpoints.get + '?what=' +
        encodeURIComponent(what) + '&access_token=' + swtr.access_token;
      // get them!
      this.sync('read', this, {
        url: url,
        success: function() {
          if(typeof options.success === 'function') {
            options.success.apply(this, arguments);
          }
        },
        error: function() {
          if(typeof options.error === 'function') {
            options.error.apply(this, arguments);
          }
        }
      });
    }
  });

  var LDView = Backbone.View.extend({
    id: 'linked-data-container',
    initialize: function() {
      var self = this;
      if(!swtr.LDs) {
        swtr.LDs = new LDSwts();
      }
      if(!swtr.LDs.length) {
        console.log(swtr.LDs);
        this.loader_template = _.template($('#loader-template').html());
        $('#linked-data-page').prepend(this.loader_template());
        swtr.LDs.getAll({
          what: 'img-anno',
          success: function(data) {
            swtr.LDs.add(data);
            if(!swtr.tagCloudView) {
              $('#spinner').remove();
              swtr.tagCloudView = new TagCloudView({collection: swtr.LDs});
            }
          }
        });
      }
    },
    destroy: function() {
      this.cleanUp();
      this.remove();
    },
    cleanUp: function() {
      if(!$('#tag-cloud').is(':visible')) {
        $('#gallery').hide();
        $('#tag-cloud').show();
      }
    }
  });

  var TagCloudView = Backbone.View.extend({
    el: $('#tag-cloud'),
    events: {
      'click #user-tag-cloud li p': 'userTagClicked',
      'click #tags-tag-cloud li p': 'tagsTagClicked'
    },
    initialize: function() {
      this.user_tag_el = $('#user-tag-cloud');
      this.tags_tag_el = $('#tags-tag-cloud');
      this.template = _.template($('#linked-data-list-template').html());
      this.render();
    },
    userTagClicked: function(e) {
      anno.reset();
      var user = $(e.currentTarget).text();
      var swts = swtr.LDs.filter(function(swt) {
        if(swt.get('who') == user) {
          return swt;
        }
      });
      swts = _.uniq(swts, function(swt) {
        return swt.get('where');
      });
      this.setGalleryView(swts);
      // $(this.el).hide();
    },
    tagsTagClicked: function(e) {
      anno.reset();
      var tag = $(e.currentTarget).text();
      var swts = swtr.LDs.filter(function(swt) {
        if(swt.get('how').tags){
          if(_.contains(swt.get('how').tags, tag)) {
              return swt;
            }
        }
      });
      swts = _.uniq(swts, function(swt) {
        return swt.get('where');
      });

      // this.setGalleryView(_.uniq(swts, 'where'));
      this.setGalleryView(swts);
      // $(this.el).hide();
    },
    setGalleryView: function(swts) {
      if(this.galleryView) {
        //set the collection of galleryView to new set of swts to be displayed.
        this.galleryView.collection = swts;
        this.galleryView.render();
      }
      else {
        this.galleryView = new GalleryView({collection: swts});
      }
    },
    render: function() {
      $(this.el).show();
      this.renderUserTagCloud();
      this.renderTagsTagCloud();
    },
    renderUserTagCloud: function() {
      // var words = _.uniq(swtr.LDs.pluck('who'));
      var weights = swtr.LDs.countBy('who');
      _.each(weights, function(weight, who) {
        $(this.user_tag_el).append(this.template({weight: weight, who: who}));
      }, this);
    },
    renderTagsTagCloud: function() {
      var sweetsWithTags = swtr.LDs.filter(function(k) {
        if(k.get('how').tags) {
          return k;
        }
      });
      var tags = [];
      _.each(sweetsWithTags, function(sweet) {
        tags.push(sweet.get('how').tags);
      });
      tags = _.countBy(_.flatten(tags));
      _.each(tags, function(weight, who) {
        $(this.tags_tag_el).append(this.template({weight: weight, who: who}));
      }, this);

    }
  });

  var GalleryView = Backbone.View.extend({
    el: $('#gallery'),
    events: {
      'click img': 'onImgClick'
    },
    setCustomField: false,
    initialize: function() {
      this.template = _.template($('#gallery-item-template').html());
      this.cover_template = _.template($('#ocd-item-cover-template').html());
      this.render();
    },
    render: function() {
      this.setUp();
      _.each(this.collection, function(model) {
        var models = swtr.LDs.filter(function(swt) {
          if(swt.get('how').src == model.get('how').src) {
            return model;
          }
        });
        var tags = [];
        _.each(models, function(model) {
          if(model.get('how').tags) {
            tags.push(model.get('how').tags);
          }
        });

        tags = _.flatten(tags);

        $(this.el).append(this.template({
          'how': {
            'tags': tags,
            'src': model.get('how').src
          },
          'who':model.get('who')
        }));

      }, this);

      $('html, body').animate({
        scrollTop: $('#gallery').offset().top
      }, 1000);

    },
    setUp: function() {
      $('#tag-list').collapse('hide');
      $('#user-list').collapse('hide');

      if(!$(this.el).is(':visible')) {
        $(this.el).show();
      }

      $(this.el).html('');

    },
    onImgClick: function(e){
      var swts = swtr.LDs.filter(function(k) {
        if(k.get('where') == $(e.currentTarget).attr('src')) {
          return k;
        }
      });
      if(!this.setCustomField) {
        anno.addPlugin("CustomFields", {});
        this.setCustomField = true;
      }
      anno.makeAnnotatable($(e.currentTarget)[0]);
      console.log(swts);
      _.each(swts, function(swt) {
        var anno_obj = swt.toJSON();
        anno_obj.how['editable'] = false;
        anno.addAnnotation(anno_obj.how);
      });
      anno.hideSelectionWidget();
      this.$(".annotorious-item-unfocus").css("opacity", '0.6');
    }
  });

  swtr.LDView = LDView;
})(window);
